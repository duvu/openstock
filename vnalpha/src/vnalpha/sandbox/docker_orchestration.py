"""Guard-bound orchestration of one canonical Docker sandbox execution."""

from __future__ import annotations

from typing import Protocol, final

from vnalpha.sandbox.artifact_writer import (
    SandboxArtifactGuardEvidenceMismatchError,
    SandboxArtifactGuardStateError,
    SandboxArtifactWriter,
    SandboxArtifactWriterStateError,
)
from vnalpha.sandbox.docker_orchestration_types import (
    SandboxDockerOrchestrationFailureCode,
    SandboxDockerOrchestrationRequest,
    SandboxDockerOrchestrationResult,
    SandboxDockerOrchestrationStatus,
    classify_execution,
    controller_status,
    validation_failure_reason,
)
from vnalpha.sandbox.docker_policy import DockerExecutionRequest
from vnalpha.sandbox.docker_runtime import DockerExecutionResult, DockerFailureCode
from vnalpha.sandbox.docker_terminalization import SandboxDockerTerminalizer
from vnalpha.sandbox.execution_evidence import (
    SandboxExecutionEvidence,
    SandboxExecutionFailureCode,
    SandboxExecutionStatus,
)
from vnalpha.sandbox.failure_observability import (
    SandboxFailureObservation,
    SandboxFailureRecordCode,
    record_failure,
)
from vnalpha.sandbox.layout import SandboxArtifactLayout
from vnalpha.sandbox.output_validation import SandboxOutputValidator
from vnalpha.sandbox.repository import SandboxJobRepository
from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

__all__ = (
    "SandboxDockerOrchestrationFailureCode",
    "SandboxDockerOrchestrationRequest",
    "SandboxDockerOrchestrationResult",
    "SandboxDockerOrchestrationStatus",
    "SandboxDockerOrchestrator",
)


class SandboxDockerRunner(Protocol):
    """The fakeable Docker runtime boundary used by orchestration."""

    def run(self, request: DockerExecutionRequest) -> DockerExecutionResult:
        """Run one already-hardened Docker execution request."""

        ...


@final
class SandboxDockerOrchestrator:
    """Execute only allowed, digest-matching jobs through canonical artifacts."""

    def __init__(
        self,
        storage: SandboxArtifactStorage,
        writer: SandboxArtifactWriter,
        runner: SandboxDockerRunner,
        validator: SandboxOutputValidator,
        repository: SandboxJobRepository,
    ) -> None:
        self._storage = storage
        self._writer = writer
        self._runner = runner
        self._validator = validator
        self._terminalizer = SandboxDockerTerminalizer(writer, repository)
        self._layout = SandboxArtifactLayout()

    def execute(
        self, request: SandboxDockerOrchestrationRequest
    ) -> SandboxDockerOrchestrationResult:
        """Run a verified job once and atomically persist its bounded evidence."""

        if request.guard_result.code_digest != request.job.code_digest:
            return _rejected(
                SandboxDockerOrchestrationFailureCode.GUARD_DIGEST_MISMATCH
            )
        if not request.guard_result.allowed:
            return _rejected(SandboxDockerOrchestrationFailureCode.GUARD_DENIED)
        try:
            self._writer.require_persisted_guard(request.guard_result)
        except SandboxArtifactGuardEvidenceMismatchError:
            return _rejected(
                SandboxDockerOrchestrationFailureCode.GUARD_EVIDENCE_MISMATCH
            )
        except (SandboxArtifactGuardStateError, SandboxArtifactWriterStateError):
            return _rejected(SandboxDockerOrchestrationFailureCode.GUARD_NOT_PERSISTED)
        output_path = self._storage.ensure_directory(
            self._layout.sandbox_writable_directory.as_posix(),
            mode=0o777,
        )
        docker_request = DockerExecutionRequest(
            image=request.image,
            code_path=self._storage.path_for(self._layout.generated_code.as_posix()),
            input_paths=tuple(
                self._storage.path_for(str(path))
                for path in request.job.filesystem_policy.approved_read_paths
            ),
            output_path=output_path,
            resource_limits=request.job.resource_limits,
        )
        execution = self._runner.run(docker_request)
        classification = classify_execution(execution)
        if classification is None:
            evidence = SandboxExecutionEvidence.from_result(
                SandboxExecutionStatus.FAILED,
                execution,
                docker_request,
                SandboxExecutionFailureCode.INVALID_RUNNER_RESULT,
            )
            if not self._persist_evidence(evidence):
                self._record_failure(
                    request,
                    SandboxExecutionStatus.FAILED,
                    SandboxFailureRecordCode.ARTIFACT_PERSISTENCE_FAILED,
                )
                return SandboxDockerOrchestrationResult(
                    status=SandboxDockerOrchestrationStatus.FAILED,
                    failure_code=SandboxDockerOrchestrationFailureCode.ARTIFACT_PERSISTENCE_FAILED,
                    execution=execution,
                )
            self._record_failure(
                request,
                SandboxExecutionStatus.FAILED,
                SandboxFailureRecordCode.INVALID_RUNNER_RESULT,
            )
            return SandboxDockerOrchestrationResult(
                status=SandboxDockerOrchestrationStatus.FAILED,
                failure_code=SandboxDockerOrchestrationFailureCode.INVALID_RUNNER_RESULT,
                execution=execution,
            )
        status, failure_code = classification
        evidence = SandboxExecutionEvidence.from_result(
            status, execution, docker_request
        )
        if not self._persist_evidence(evidence):
            self._record_failure(
                request,
                SandboxExecutionStatus.FAILED,
                SandboxFailureRecordCode.ARTIFACT_PERSISTENCE_FAILED,
            )
            return SandboxDockerOrchestrationResult(
                status=SandboxDockerOrchestrationStatus.FAILED,
                failure_code=SandboxDockerOrchestrationFailureCode.ARTIFACT_PERSISTENCE_FAILED,
                execution=execution,
            )
        if failure_code is not None:
            self._record_failure(request, status, failure_code)
            return SandboxDockerOrchestrationResult(
                status=controller_status(status),
                failure_code=failure_code,
                execution=execution,
            )
        validation = self._validator.validate(request.job.output_schema)
        if not self._terminalizer.persist_finalization(
            validation, request.job.output_schema
        ):
            return self._failed_after_terminalization(
                request,
                execution,
                SandboxDockerOrchestrationFailureCode.ARTIFACT_PERSISTENCE_FAILED,
            )
        if validation.succeeded:
            result = validation.result
            if result is None:
                return self._failed_after_terminalization(
                    request,
                    execution,
                    SandboxDockerOrchestrationFailureCode.ARTIFACT_PERSISTENCE_FAILED,
                )
            if not self._terminalizer.mark_succeeded(request.job, result.summary):
                return SandboxDockerOrchestrationResult(
                    status=SandboxDockerOrchestrationStatus.FAILED,
                    failure_code=SandboxDockerOrchestrationFailureCode.JOB_STATUS_PERSISTENCE_FAILED,
                    execution=execution,
                )
            return SandboxDockerOrchestrationResult(
                status=SandboxDockerOrchestrationStatus.SUCCEEDED,
                failure_code=None,
                execution=execution,
            )
        if not self._terminalizer.mark_failed(
            request.job, validation_failure_reason(validation.evidence.failure_code)
        ):
            return SandboxDockerOrchestrationResult(
                status=SandboxDockerOrchestrationStatus.FAILED,
                failure_code=SandboxDockerOrchestrationFailureCode.JOB_STATUS_PERSISTENCE_FAILED,
                execution=execution,
            )
        return SandboxDockerOrchestrationResult(
            status=SandboxDockerOrchestrationStatus.FAILED,
            failure_code=SandboxDockerOrchestrationFailureCode.OUTPUT_VALIDATION_FAILED,
            execution=execution,
        )

    def _persist_evidence(self, evidence: SandboxExecutionEvidence) -> bool:
        """Persist complete runner evidence without allowing persistence success to leak."""

        try:
            self._writer.persist_execution(evidence)
        except (
            SandboxArtifactGuardEvidenceMismatchError,
            SandboxArtifactGuardStateError,
            SandboxArtifactPathError,
            SandboxArtifactWriterStateError,
        ):
            return False
        return True

    def _failed_after_terminalization(
        self,
        request: SandboxDockerOrchestrationRequest,
        execution: DockerExecutionResult,
        failure_code: SandboxDockerOrchestrationFailureCode,
    ) -> SandboxDockerOrchestrationResult:
        if not self._terminalizer.mark_failed(
            request.job, "sandbox output finalization could not be persisted"
        ):
            return SandboxDockerOrchestrationResult(
                status=SandboxDockerOrchestrationStatus.FAILED,
                failure_code=SandboxDockerOrchestrationFailureCode.JOB_STATUS_PERSISTENCE_FAILED,
                execution=execution,
            )
        return SandboxDockerOrchestrationResult(
            status=SandboxDockerOrchestrationStatus.FAILED,
            failure_code=failure_code,
            execution=execution,
        )

    def _record_failure(
        self,
        request: SandboxDockerOrchestrationRequest,
        status: SandboxExecutionStatus,
        failure_code: DockerFailureCode | SandboxFailureRecordCode,
    ) -> None:
        """Record typed runner metadata after evidence persistence is complete."""

        record_failure(
            SandboxFailureObservation(
                run_context=self._storage.run_context,
                job_id=request.job.job_id,
                correlation_id=request.job.correlation_id,
                status=status,
                failure_code=failure_code,
            )
        )


def _rejected(
    failure_code: SandboxDockerOrchestrationFailureCode,
) -> SandboxDockerOrchestrationResult:
    return SandboxDockerOrchestrationResult(
        status=SandboxDockerOrchestrationStatus.REJECTED,
        failure_code=failure_code,
        execution=None,
    )
