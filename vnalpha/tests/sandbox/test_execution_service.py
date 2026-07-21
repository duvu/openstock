from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import final

import duckdb

from vnalpha.assistant.models import (
    AssistantPlan,
    AssistantRequest,
    IntentResult,
    PreparedAssistantTurn,
    ToolPlanStep,
    plan_hash,
)
from vnalpha.observability.context import RunContext
from vnalpha.sandbox.docker_runner import (
    DockerExecutionRequest,
    DockerExecutionResult,
    DockerFailureCode,
    parse_docker_image_reference,
)
from vnalpha.sandbox.repository import SandboxJobRepository
from vnalpha.warehouse.migrations import run_migrations

_IMAGE = parse_docker_image_reference(
    f"registry.example/openstock/vnalpha-sandbox@sha256:{'a' * 64}"
)
_STDOUT_SECRET = "stdout-secret-must-not-leak"
_STDERR_SECRET = "stderr-secret-must-not-leak"


def _sandbox_plan(purpose: str) -> AssistantPlan:
    return AssistantPlan(
        intent="sandbox_research_calculation",
        steps=[
            ToolPlanStep(
                step_id="step_sandbox",
                tool_name="sandbox.run_research_code",
                arguments={"purpose": purpose},
                purpose="Prepare an approval-gated sandbox research calculation",
                required_permission="SANDBOX_APPROVAL",
            )
        ],
    )


def _prepared_turn(plan: AssistantPlan) -> PreparedAssistantTurn:
    return PreparedAssistantTurn(
        prepared_turn_id="prepared-sandbox-turn",
        assistant_session_id="assistant-session",
        request=AssistantRequest(current_user_prompt="run sandbox analysis"),
        intent_result=IntentResult(
            intent="sandbox_research_calculation",
            confidence=1.0,
            entities={},
        ),
        plan=plan,
        plan_hash=plan_hash(plan),
        policy_status="PASS",
        created_at="2026-07-12T00:00:00+00:00",
    )


@final
@dataclass(frozen=True, slots=True)
class _GeneratedProgram:
    code: str
    summary: str
    input_references: tuple[str, ...] = ()


@final
@dataclass(slots=True)
class _WritingRunner:
    calls: list[DockerExecutionRequest] = field(default_factory=list)

    def run(self, request: DockerExecutionRequest) -> DockerExecutionResult:
        self.calls.append(request)
        output_dir = request.output_path
        output_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "schema_version": 1,
            "summary": "Sandbox calculation completed for approved purpose.",
            "artifacts": [],
            "purpose": "approved-purpose",
        }
        (output_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "summary.md").write_text(
            "# Sandbox Result\n\nValidated output only.\n",
            encoding="utf-8",
        )
        return DockerExecutionResult(
            return_code=0,
            stdout=_STDOUT_SECRET.encode("utf-8"),
            stderr=_STDERR_SECRET.encode("utf-8"),
        )


@final
@dataclass(slots=True)
class _RuntimeFailureRunner:
    calls: list[DockerExecutionRequest] = field(default_factory=list)

    def run(self, request: DockerExecutionRequest) -> DockerExecutionResult:
        self.calls.append(request)
        request.output_path.mkdir(parents=True, exist_ok=True)
        return DockerExecutionResult(
            return_code=-1,
            stdout=_STDOUT_SECRET.encode("utf-8"),
            stderr=_STDERR_SECRET.encode("utf-8"),
            failure_code=DockerFailureCode.RUNTIME_FAILED,
            detail="sandbox runtime failed",
        )


def _service(tmp_path: Path, conn: duckdb.DuckDBPyConnection, **kwargs):
    from vnalpha.sandbox.execution_service import SandboxExecutionService

    run_ctx = RunContext(
        run_id="run-sandbox-service",
        surface="test",
        actor="pytest",
        log_root=tmp_path,
    )
    return SandboxExecutionService(
        conn,
        surface="test",
        run_context=run_ctx,
        image=_IMAGE,
        **kwargs,
    )


def test_materialize_assistant_plan_persists_queued_job_preview_and_request_evidence(
    tmp_path: Path,
) -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    service = _service(tmp_path, conn)

    plan = service.materialize_assistant_plan(_sandbox_plan("mean of 1, 2, 3"))

    step = plan.steps[0]
    assert step.arguments["job_id"]
    assert step.arguments["code_digest"]
    assert step.arguments["code_summary"]
    assert step.arguments["input_references"] == []
    assert step.arguments["image_digest"] == f"sha256:{'a' * 64}"
    assert step.arguments["resource_limits"] == {
        "cpu_millis": 500,
        "memory_mb": 256,
        "timeout_seconds": 30,
    }

    stored = SandboxJobRepository(conn).get(step.arguments["job_id"])
    assert stored is not None
    assert stored.status.value == "queued"

    artifact_root = (
        tmp_path / "runs/run-sandbox-service/sandbox" / step.arguments["job_id"]
    )
    assert (artifact_root / "request.json").exists()
    assert (artifact_root / "generated_code.py").exists()
    assert (artifact_root / "inputs/references.json").exists()

    lifecycle = [
        json.loads(line)
        for line in (artifact_root / "lifecycle.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["event_type"] for event in lifecycle] == ["SANDBOX_JOB_CREATED"]
    assert lifecycle[0]["correlation_id"] == step.arguments["correlation_id"]
