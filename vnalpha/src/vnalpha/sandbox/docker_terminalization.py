from __future__ import annotations

from dataclasses import dataclass

from vnalpha.sandbox.artifact_finalization import (
    SandboxArtifactObservedEntryConflictError,
)
from vnalpha.sandbox.artifact_writer import (
    SandboxArtifactGuardStateError,
    SandboxArtifactWriter,
    SandboxArtifactWriterStateError,
)
from vnalpha.sandbox.contracts import SandboxOutputSchema
from vnalpha.sandbox.models import (
    SandboxJob,
    SandboxJobNotFoundError,
    SandboxJobTransitionError,
)
from vnalpha.sandbox.output_validation import SandboxOutputValidationResult
from vnalpha.sandbox.repository import SandboxJobRepository
from vnalpha.sandbox.storage import (
    SandboxArtifactNotFoundError,
    SandboxArtifactPathError,
    SandboxArtifactSizeError,
    SandboxArtifactTypeError,
)


@dataclass(frozen=True, slots=True)
class SandboxDockerTerminalizer:
    writer: SandboxArtifactWriter
    repository: SandboxJobRepository

    def persist_finalization(
        self,
        validation: SandboxOutputValidationResult,
        output_schema: SandboxOutputSchema,
    ) -> bool:
        try:
            _ = self.writer.persist_validation_and_manifest(validation, output_schema)
        except (
            SandboxArtifactGuardStateError,
            SandboxArtifactNotFoundError,
            SandboxArtifactObservedEntryConflictError,
            SandboxArtifactPathError,
            SandboxArtifactSizeError,
            SandboxArtifactTypeError,
            SandboxArtifactWriterStateError,
        ):
            return False
        return True

    def mark_succeeded(self, job: SandboxJob, summary: str) -> bool:
        try:
            self.repository.mark_succeeded(job.job_id, summary)
        except (SandboxJobNotFoundError, SandboxJobTransitionError):
            return False
        return True

    def mark_failed(self, job: SandboxJob, reason: str) -> bool:
        try:
            self.repository.mark_failed(job.job_id, reason)
        except (SandboxJobNotFoundError, SandboxJobTransitionError):
            return False
        return True
