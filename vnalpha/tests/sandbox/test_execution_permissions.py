from __future__ import annotations

import json
import stat
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
    parse_docker_image_reference,
)
from vnalpha.warehouse.migrations import run_migrations

_IMAGE = parse_docker_image_reference(
    f"registry.example/openstock/vnalpha-sandbox@sha256:{'a' * 64}"
)


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
@dataclass(slots=True)
class _PermissionCapturingRunner:
    code_mode: int | None = None
    output_mode: int | None = None
    calls: list[DockerExecutionRequest] = field(default_factory=list)

    def run(self, request: DockerExecutionRequest) -> DockerExecutionResult:
        self.calls.append(request)
        self.code_mode = stat.S_IMODE(request.code_path.stat().st_mode)
        self.output_mode = stat.S_IMODE(request.output_path.stat().st_mode)
        result = {
            "schema_version": 1,
            "summary": "Sandbox calculation completed for approved purpose.",
            "artifacts": [],
            "purpose": "approved-purpose",
        }
        (request.output_path / "result.json").write_text(
            json.dumps(result, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (request.output_path / "summary.md").write_text(
            "# Sandbox Result\n\nValidated output only.\n",
            encoding="utf-8",
        )
        return DockerExecutionResult(return_code=0, stdout=b"", stderr=b"")


def test_execution_service_prepares_container_accessible_code_and_output_permissions(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.execution_service import SandboxExecutionService

    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    runner = _PermissionCapturingRunner()
    run_context = RunContext(
        run_id="run-sandbox-permissions",
        surface="test",
        actor="pytest",
        log_root=tmp_path,
    )
    service = SandboxExecutionService(
        conn,
        surface="test",
        run_context=run_context,
        image=_IMAGE,
        docker_runner=runner,
    )

    plan = service.materialize_assistant_plan(_sandbox_plan("mean of 1, 2, 3"))
    prepared = _prepared_turn(plan)
    service.approve_prepared_turn(prepared)
    _ = service.execute_prepared_turn(prepared)

    assert runner.calls
    assert runner.code_mode == 0o644
    assert runner.output_mode == 0o777
