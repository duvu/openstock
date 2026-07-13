from __future__ import annotations

from dataclasses import dataclass

import duckdb

from vnalpha.assistant.models import AssistantAnswer, PreparedAssistantTurn
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.docker_orchestration import (
    SandboxDockerOrchestrationRequest,
    SandboxDockerOrchestrator,
)
from vnalpha.sandbox.execution_answers import (
    failed_answer,
    rejected_answer,
    success_answer,
)
from vnalpha.sandbox.execution_approval import require_bound_approval
from vnalpha.sandbox.execution_context import SandboxRuntimeContext
from vnalpha.sandbox.execution_errors import SandboxExecutionError
from vnalpha.sandbox.execution_lifecycle import (
    SandboxLifecycleEvent,
    failure_code_value,
    failure_reason,
    persist_lifecycle_event,
    record_from_job,
)
from vnalpha.sandbox.models import SandboxJob, SandboxJobStatus
from vnalpha.sandbox.output_validation import SandboxOutputValidator
from vnalpha.sandbox.repository import SandboxJobRepository
from vnalpha.sandbox.retained_binding import (
    RetainedBindingRequest,
    load_retained_sandbox_job,
)
from vnalpha.sandbox.static_guard import SandboxStaticGuard
from vnalpha.sandbox.storage import SandboxArtifactStorage


@dataclass(frozen=True, slots=True)
class PreparedSandboxExecutionRequest:
    conn: duckdb.DuckDBPyConnection
    prepared: PreparedAssistantTurn
    runtime: SandboxRuntimeContext


def execute_prepared_sandbox_turn(
    request: PreparedSandboxExecutionRequest,
) -> AssistantAnswer:
    prepared = request.prepared
    if len(prepared.plan.steps) != 1:
        raise SandboxExecutionError(
            "sandbox execution requires exactly one prepared step"
        )
    step = prepared.plan.steps[0]
    if step.tool_name != "sandbox.run_research_code":
        raise SandboxExecutionError("prepared plan is not a sandbox execution request")
    retained = load_retained_sandbox_job(
        RetainedBindingRequest(
            conn=request.conn,
            arguments=step.arguments,
            run_context=request.runtime.resolve_run_context(),
            default_image=request.runtime.image,
        )
    )
    job = retained.job
    require_bound_approval(request.conn, prepared, job)
    repository = SandboxJobRepository(request.conn)
    repository.claim_for_validation(job.job_id)
    with SandboxArtifactStorage(
        request.runtime.for_run(job.run_id), job.job_id
    ) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        validator = SandboxOutputValidator(storage)
        guard = SandboxStaticGuard.evaluate(job.code)
        writer.persist_guard(guard)
        if not guard.allowed:
            repository.mark_rejected(
                job.job_id, "sandbox static guard rejected generated code"
            )
            persist_lifecycle_event(
                writer,
                job,
                SandboxLifecycleEvent(
                    event_type="SANDBOX_GUARD_REJECTED",
                    status=SandboxJobStatus.REJECTED.value,
                    summary="Sandbox job was rejected by the static guard.",
                    metadata={
                        "code_digest": guard.code_digest,
                        "rule_codes": sorted(
                            {violation.rule.value for violation in guard.violations}
                        ),
                        "violation_count": len(guard.violations),
                    },
                ),
            )
            _persist_manifest(writer, validator, job)
            return rejected_answer(job)
        persist_lifecycle_event(
            writer,
            job,
            SandboxLifecycleEvent(
                event_type="SANDBOX_JOB_STARTED",
                status=SandboxJobStatus.RUNNING.value,
                summary="Sandbox job execution started.",
                metadata={
                    "image_digest": str(retained.image).split("@", 1)[1],
                    "runtime_kind": "docker",
                },
            ),
        )
        result = SandboxDockerOrchestrator(
            storage,
            writer,
            request.runtime.runner(),
            validator,
            repository,
        ).execute(
            SandboxDockerOrchestrationRequest(
                job=job, guard_result=guard, image=retained.image
            )
        )
        if result.status.value == "succeeded":
            persist_lifecycle_event(
                writer,
                job,
                SandboxLifecycleEvent(
                    event_type="SANDBOX_JOB_SUCCEEDED",
                    status=SandboxJobStatus.SUCCEEDED.value,
                    summary="Sandbox job completed successfully.",
                    metadata={"image_digest": str(retained.image).split("@", 1)[1]},
                ),
            )
            _persist_manifest(writer, validator, job)
            return success_answer(job, storage, step.step_id)
        reason = failure_reason(result.failure_code)
        stored = repository.get(job.job_id)
        active_statuses = {
            SandboxJobStatus.QUEUED,
            SandboxJobStatus.VALIDATING,
            SandboxJobStatus.RUNNING,
        }
        if result.status.value == "rejected":
            if stored is not None and stored.status in active_statuses:
                repository.mark_rejected(job.job_id, reason)
        elif stored is not None and stored.status in active_statuses:
            repository.mark_failed(job.job_id, reason)
        persist_lifecycle_event(
            writer,
            job,
            SandboxLifecycleEvent(
                event_type="SANDBOX_JOB_FAILED",
                status=(
                    repository.get(job.job_id) or stored or record_from_job(job)
                ).status.value,
                summary="Sandbox job did not produce a validated result.",
                metadata={
                    "failure_code": failure_code_value(result.failure_code),
                    "image_digest": str(retained.image).split("@", 1)[1],
                },
            ),
        )
        _persist_manifest(writer, validator, job)
        return failed_answer(job, reason)


def _persist_manifest(
    writer: SandboxArtifactWriter,
    validator: SandboxOutputValidator,
    job: SandboxJob,
) -> None:
    validation = validator.validate(job.output_schema)
    writer.persist_validation_and_manifest(validation, job.output_schema)
