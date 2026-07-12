from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never, final

from vnalpha.sandbox.docker_policy import DockerImageReference
from vnalpha.sandbox.docker_runtime import DockerExecutionResult, DockerFailureCode
from vnalpha.sandbox.execution_evidence import SandboxExecutionStatus
from vnalpha.sandbox.models import SandboxJob
from vnalpha.sandbox.output_validation import SandboxOutputValidationFailureCode
from vnalpha.sandbox.static_guard import SandboxGuardResult


class SandboxDockerOrchestrationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


class SandboxDockerOrchestrationFailureCode(StrEnum):
    GUARD_DENIED = "guard_denied"
    GUARD_DIGEST_MISMATCH = "guard_digest_mismatch"
    GUARD_EVIDENCE_MISMATCH = "guard_evidence_mismatch"
    GUARD_NOT_PERSISTED = "guard_not_persisted"
    INVALID_RUNNER_RESULT = "invalid_runner_result"
    ARTIFACT_PERSISTENCE_FAILED = "artifact_persistence_failed"
    OUTPUT_VALIDATION_FAILED = "output_validation_failed"
    JOB_STATUS_PERSISTENCE_FAILED = "job_status_persistence_failed"


@final
@dataclass(frozen=True, slots=True)
class SandboxDockerOrchestrationRequest:
    job: SandboxJob
    guard_result: SandboxGuardResult
    image: DockerImageReference


@final
@dataclass(frozen=True, slots=True)
class SandboxDockerOrchestrationResult:
    status: SandboxDockerOrchestrationStatus
    failure_code: DockerFailureCode | SandboxDockerOrchestrationFailureCode | None
    execution: DockerExecutionResult | None


def classify_execution(
    execution: DockerExecutionResult,
) -> tuple[SandboxExecutionStatus, DockerFailureCode | None] | None:
    match execution.failure_code:
        case None:
            if execution.return_code == 0:
                return SandboxExecutionStatus.SUCCEEDED, None
            return None
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
            return SandboxExecutionStatus.REJECTED, execution.failure_code
        case DockerFailureCode.RUNTIME_TIMEOUT | DockerFailureCode.RUNTIME_FAILED:
            return SandboxExecutionStatus.FAILED, execution.failure_code
    assert_never(execution.failure_code)


def controller_status(
    status: SandboxExecutionStatus,
) -> SandboxDockerOrchestrationStatus:
    match status:
        case SandboxExecutionStatus.SUCCEEDED:
            return SandboxDockerOrchestrationStatus.SUCCEEDED
        case SandboxExecutionStatus.REJECTED:
            return SandboxDockerOrchestrationStatus.REJECTED
        case SandboxExecutionStatus.FAILED:
            return SandboxDockerOrchestrationStatus.FAILED
    assert_never(status)


def validation_failure_reason(code: SandboxOutputValidationFailureCode | None) -> str:
    match code:
        case SandboxOutputValidationFailureCode.MISSING_ARTIFACT:
            return "sandbox output validation failed: expected artifact missing"
        case (
            SandboxOutputValidationFailureCode.INVALID_RESULT
            | SandboxOutputValidationFailureCode.INVALID_SUMMARY
        ):
            return "sandbox output validation failed: invalid result"
        case SandboxOutputValidationFailureCode.ARTIFACT_REFERENCE_MISMATCH:
            return "sandbox output validation failed: artifact reference mismatch"
        case (
            SandboxOutputValidationFailureCode.UNSAFE_ARTIFACT
            | SandboxOutputValidationFailureCode.ARTIFACT_TOO_LARGE
        ):
            return "sandbox output validation failed: unsafe artifact"
        case None:
            return "sandbox output validation failed"
    assert_never(code)
