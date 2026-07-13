from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime
from typing import Callable, Final
from uuid import uuid4

import duckdb

from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    PreparedAssistantTurn,
)
from vnalpha.observability.context import RunContext
from vnalpha.sandbox.approval import SandboxApproval
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.binding import SandboxTurnRequest, prepare_sandbox_turn
from vnalpha.sandbox.docker_runner import (
    DockerImageReference,
    parse_docker_image_reference,
)
from vnalpha.sandbox.execution_approval import (
    SandboxApprovalContext,
    create_bound_approval,
)
from vnalpha.sandbox.execution_context import (
    SandboxDockerRunner,
    SandboxRuntimeConfiguration,
    SandboxRuntimeContext,
)
from vnalpha.sandbox.execution_errors import SandboxExecutionError
from vnalpha.sandbox.execution_lifecycle import (
    SandboxLifecycleEvent,
    persist_lifecycle_event,
)
from vnalpha.sandbox.execution_types import SandboxGeneratedProgram, SandboxPreview
from vnalpha.sandbox.generation import generate_numeric_research_program
from vnalpha.sandbox.models import (
    SandboxJobId,
    SandboxJobRequest,
    SandboxJobStatus,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.prepared_execution import (
    PreparedSandboxExecutionRequest,
    execute_prepared_sandbox_turn,
)
from vnalpha.sandbox.repository import SandboxJobRepository
from vnalpha.sandbox.retained_binding import (
    RetainedBindingRequest,
    load_retained_sandbox_job,
)
from vnalpha.sandbox.storage import SandboxArtifactStorage

_DEFAULT_IMAGE: Final = f"registry.example/openstock/vnalpha-sandbox@sha256:{'a' * 64}"
_DEFAULT_LIMITS: Final = SandboxResourceLimits(
    cpu_millis=500,
    memory_mb=256,
    timeout_seconds=30,
)
_DEFAULT_APPROVER: Final = "user"


class SandboxExecutionService:
    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        surface: str,
        run_context: RunContext | None = None,
        image: DockerImageReference | str | None = None,
        docker_runner: SandboxDockerRunner | None = None,
        code_generator: Callable[[str], SandboxGeneratedProgram] | None = None,
    ) -> None:
        self._conn = conn
        self._surface = surface
        raw_image = str(
            image or os.environ.get("VNALPHA_SANDBOX_IMAGE", _DEFAULT_IMAGE)
        )
        self._runtime = SandboxRuntimeContext(
            SandboxRuntimeConfiguration(
                surface=surface,
                run_context=run_context,
                image=parse_docker_image_reference(raw_image),
                docker_runner=docker_runner,
            )
        )
        self._code_generator = code_generator or generate_numeric_research_program

    def materialize_assistant_plan(self, plan: AssistantPlan) -> AssistantPlan:
        if len(plan.steps) != 1:
            return plan
        step = plan.steps[0]
        if step.tool_name != "sandbox.run_research_code" or "job_id" in step.arguments:
            return plan
        purpose = str(
            step.arguments.get("purpose", "offline research calculation")
        ).strip()
        preview = self.prepare_job(purpose)
        return replace(plan, steps=[replace(step, arguments=preview.arguments)])

    def prepare_job(self, purpose: str) -> SandboxPreview:
        correlation_id = self._runtime.ensure_correlation_id()
        run_context = self._runtime.resolve_run_context()
        program = self._code_generator(purpose)
        request = SandboxJobRequest.model_validate(
            {
                "purpose": purpose,
                "code": program.code,
                "correlation_id": str(correlation_id),
                "resource_limits": _DEFAULT_LIMITS.model_dump(),
                "approved_input_paths": tuple(program.input_references),
            }
        )
        job = request.into_job(
            job_id=SandboxJobId(f"job-{uuid4().hex}"),
            run_id=SandboxRunId(run_context.run_id),
        )
        SandboxJobRepository(self._conn).create(job)
        with SandboxArtifactStorage(run_context, job.job_id) as storage:
            writer = SandboxArtifactWriter(storage)
            writer.persist_request(job)
            persist_lifecycle_event(
                writer,
                job,
                SandboxLifecycleEvent(
                    event_type="SANDBOX_JOB_CREATED",
                    status=SandboxJobStatus.QUEUED.value,
                    summary="Sandbox job created and awaiting approval.",
                    metadata={
                        "code_digest": job.code_digest,
                        "image_digest": str(self._runtime.image).split("@", 1)[1],
                        "cpu_millis": job.resource_limits.cpu_millis,
                        "memory_mb": job.resource_limits.memory_mb,
                        "timeout_seconds": job.resource_limits.timeout_seconds,
                        "input_reference_count": len(
                            job.filesystem_policy.approved_read_paths
                        ),
                        "network_enabled": job.network_enabled,
                    },
                ),
            )
        return SandboxPreview(
            job=job, code_summary=program.summary, image=self._runtime.image
        )

    def prepare_turn(self, purpose: str, *, raw_request: str) -> PreparedAssistantTurn:
        return prepare_sandbox_turn(
            self._conn,
            self,
            SandboxTurnRequest(
                purpose=purpose,
                raw_request=raw_request,
                surface=self._surface,
            ),
        )

    def execute_prepared_turn(self, prepared: PreparedAssistantTurn) -> AssistantAnswer:
        return execute_prepared_sandbox_turn(
            PreparedSandboxExecutionRequest(
                conn=self._conn, prepared=prepared, runtime=self._runtime
            )
        )

    def approve_prepared_turn(
        self,
        prepared: PreparedAssistantTurn,
        *,
        approver: str = _DEFAULT_APPROVER,
        approved_at: datetime | None = None,
    ) -> SandboxApproval:
        if len(prepared.plan.steps) != 1:
            raise SandboxExecutionError(
                "sandbox execution requires exactly one prepared step"
            )
        step = prepared.plan.steps[0]
        if step.tool_name != "sandbox.run_research_code":
            raise SandboxExecutionError(
                "prepared plan is not a sandbox execution request"
            )
        retained = load_retained_sandbox_job(
            RetainedBindingRequest(
                conn=self._conn,
                arguments=step.arguments,
                run_context=self._runtime.resolve_run_context(),
                default_image=self._runtime.image,
            )
        )
        return create_bound_approval(
            self._conn,
            prepared,
            retained.job,
            SandboxApprovalContext(approver=approver, approved_at=approved_at),
        )
