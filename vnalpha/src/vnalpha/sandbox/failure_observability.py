"""Metadata-only observability for classified sandbox Docker failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import assert_never, final
from uuid import uuid4

from vnalpha.observability.context import RunContext
from vnalpha.observability.jsonl import append_jsonl
from vnalpha.sandbox.docker_runtime import DockerFailureCode
from vnalpha.sandbox.execution_evidence import SandboxExecutionStatus
from vnalpha.sandbox.models import SandboxCorrelationId, SandboxJobId


class SandboxFailureRecordCode(StrEnum):
    """Controller outcomes eligible for Docker failure observability."""

    INVALID_RUNNER_RESULT = "invalid_runner_result"
    ARTIFACT_PERSISTENCE_FAILED = "artifact_persistence_failed"


@final
@dataclass(frozen=True, slots=True)
class SandboxFailureObservation:
    """Typed metadata needed to record a classified terminal runner failure."""

    run_context: RunContext
    job_id: SandboxJobId
    correlation_id: SandboxCorrelationId
    status: SandboxExecutionStatus
    failure_code: DockerFailureCode | SandboxFailureRecordCode


def record_failure(observation: SandboxFailureObservation) -> None:
    """Append one fixed, metadata-only error-family record for a classified failure."""

    error_type, error_message = _classification(observation.failure_code)
    record: dict[str, str] = {
        "event_id": uuid4().hex,
        "run_id": observation.run_context.run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "level": "ERROR",
        "event_type": "EXCEPTION_CAPTURED",
        "surface": observation.run_context.surface,
        "correlation_id": str(observation.correlation_id),
        "error_type": error_type,
        "error_message": error_message,
        "module": "vnalpha.sandbox.docker_orchestration",
        "function": "execute",
        "stacktrace": "",
        "stacktrace_hash": "",
        "likely_cause": "",
        "suggested_next_step": "",
        "redaction_status": "metadata",
        "job_id": str(observation.job_id),
        "status": observation.status.value,
        "failure_code": observation.failure_code.value,
        "runtime_kind": "docker",
    }
    try:
        append_jsonl(observation.run_context.errors_path, record)
    except OSError:
        return


def _classification(
    failure_code: DockerFailureCode | SandboxFailureRecordCode,
) -> tuple[str, str]:
    match failure_code:
        case (
            DockerFailureCode.HOST_NOT_LINUX
            | DockerFailureCode.DOCKER_LAUNCH_FAILED
            | DockerFailureCode.DOCKER_NOT_FOUND
            | DockerFailureCode.DAEMON_UNAVAILABLE
            | DockerFailureCode.DAEMON_TIMEOUT
            | DockerFailureCode.SERVER_NOT_LINUX
            | DockerFailureCode.IMAGE_NOT_AVAILABLE
            | DockerFailureCode.IMAGE_PROBE_TIMEOUT
        ):
            return (
                "SandboxDockerPreflightFailure",
                "Sandbox Docker preflight rejected execution",
            )
        case DockerFailureCode.RUNTIME_TIMEOUT | DockerFailureCode.RUNTIME_FAILED:
            return "SandboxDockerRuntimeFailure", "Sandbox Docker execution failed"
        case SandboxFailureRecordCode.INVALID_RUNNER_RESULT:
            return (
                "SandboxDockerRunnerContractFailure",
                "Sandbox Docker runner returned an invalid result",
            )
        case SandboxFailureRecordCode.ARTIFACT_PERSISTENCE_FAILED:
            return (
                "SandboxExecutionPersistenceFailure",
                "Sandbox execution evidence could not be persisted",
            )
        case unreachable:
            assert_never(unreachable)
