from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeAlias
from uuid import uuid4

from vnalpha.observability.audit import log_audit
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.docker_orchestration_types import (
    SandboxDockerOrchestrationFailureCode,
)
from vnalpha.sandbox.docker_runner import DockerFailureCode
from vnalpha.sandbox.models import SandboxJob
from vnalpha.sandbox.repository import SandboxJobRecord

LifecycleMetadataValue: TypeAlias = str | int | bool | None | list[str]
SandboxFailureCode: TypeAlias = (
    DockerFailureCode | SandboxDockerOrchestrationFailureCode | None
)


@dataclass(frozen=True, slots=True)
class SandboxLifecycleEvent:
    event_type: str
    status: str
    summary: str
    metadata: dict[str, LifecycleMetadataValue]


def persist_lifecycle_event(
    writer: SandboxArtifactWriter,
    job: SandboxJob,
    event: SandboxLifecycleEvent,
) -> None:
    payload = {
        "event_id": uuid4().hex,
        "created_at": datetime.now(UTC).isoformat(),
        "event_type": event.event_type,
        "job_id": str(job.job_id),
        "run_id": str(job.run_id),
        "correlation_id": str(job.correlation_id),
        "status": event.status,
        "summary": event.summary,
        "metadata": event.metadata,
    }
    writer.persist_lifecycle_event(payload)
    log_audit(
        event.event_type,
        event.summary,
        status=event.status,
        object_type="sandbox_job",
        object_id=str(job.job_id),
        extra={
            "job_id": str(job.job_id),
            "correlation_id": str(job.correlation_id),
            **event.metadata,
        },
        module="vnalpha.sandbox.execution_service",
        function=(
            "prepare_job"
            if event.event_type == "SANDBOX_JOB_CREATED"
            else "execute_prepared_turn"
        ),
    )


def failure_reason(failure_code: SandboxFailureCode) -> str:
    if failure_code is None:
        return "sandbox execution did not produce a validated result"
    if failure_code in {
        DockerFailureCode.HOST_NOT_LINUX,
        DockerFailureCode.DOCKER_LAUNCH_FAILED,
        DockerFailureCode.DOCKER_NOT_FOUND,
        DockerFailureCode.DAEMON_UNAVAILABLE,
        DockerFailureCode.DAEMON_TIMEOUT,
        DockerFailureCode.SERVER_NOT_LINUX,
        DockerFailureCode.IMAGE_NOT_AVAILABLE,
        DockerFailureCode.IMAGE_PROBE_TIMEOUT,
    }:
        return "sandbox execution boundary rejected the job"
    if failure_code in {
        DockerFailureCode.RUNTIME_TIMEOUT,
        DockerFailureCode.RUNTIME_FAILED,
    }:
        return "sandbox runtime failed"
    return failure_code.value


def failure_code_value(failure_code: SandboxFailureCode) -> str | None:
    return None if failure_code is None else failure_code.value


def record_from_job(job: SandboxJob) -> SandboxJobRecord:
    return SandboxJobRecord(
        job_id=job.job_id,
        run_id=job.run_id,
        correlation_id=job.correlation_id,
        purpose=job.purpose,
        code_digest=job.code_digest,
        status=job.status,
        filesystem_policy=job.filesystem_policy,
        output_schema=job.output_schema,
        result_summary=None,
        rejection_reason=None,
        failure_reason=None,
    )
