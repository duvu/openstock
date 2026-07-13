"""Trusted composition of the host-authored sandbox artifact manifest."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import final

from typing_extensions import override

from vnalpha.sandbox.artifact_manifest import (
    SandboxArtifactManifest,
    SandboxArtifactManifestEntry,
)
from vnalpha.sandbox.contracts import SandboxExpectedArtifact, SandboxOutputSchema
from vnalpha.sandbox.output_validation import SandboxOutputValidationResult
from vnalpha.sandbox.storage import SandboxArtifactStorage

_MAX_RESULT_JSON_BYTES = 1_048_576
_MAX_SUMMARY_MARKDOWN_BYTES = 262_144
_MAX_OPTIONAL_ARTIFACT_BYTES = 10_485_760


@final
class SandboxArtifactObservedEntryConflictError(ValueError):
    """Validation evidence does not map to a unique schema-approved artifact set."""

    @override
    def __str__(self) -> str:
        return "sandbox observed artifact inventory contains a conflicting path"


@final
@dataclass(frozen=True, slots=True)
class SandboxArtifactManifestFinalizer:
    """Rebuild manifest output entries from trusted storage and the output schema."""

    storage: SandboxArtifactStorage
    output_schema: SandboxOutputSchema

    def build(
        self,
        host_entries: tuple[SandboxArtifactManifestEntry, ...],
        validation: SandboxOutputValidationResult,
    ) -> SandboxArtifactManifest:
        """Compose a manifest without trusting result-supplied inventory metadata."""

        paths = validation.evidence.validated_paths
        if len(paths) != len(set(paths)):
            raise SandboxArtifactObservedEntryConflictError()
        host_paths = {entry.path for entry in host_entries}
        if any(path in host_paths for path in paths):
            raise SandboxArtifactObservedEntryConflictError()
        artifacts = {
            str(artifact.path): artifact for artifact in self.output_schema.artifacts
        }
        if any(path not in artifacts for path in paths):
            raise SandboxArtifactObservedEntryConflictError()
        observed_entries = tuple(self._read_entry(path, artifacts) for path in paths)
        return SandboxArtifactManifest(entries=(*host_entries, *observed_entries))

    def _read_entry(
        self,
        path: str,
        artifacts: dict[str, SandboxExpectedArtifact],
    ) -> SandboxArtifactManifestEntry:
        """Read one schema-approved artifact and derive its immutable manifest entry."""

        artifact = artifacts.get(path)
        if artifact is None:
            raise SandboxArtifactObservedEntryConflictError()
        content = self.storage.read_bounded_regular_file(
            path, max_bytes=_max_bytes(artifact)
        )
        return SandboxArtifactManifestEntry(
            path=path,
            sha256=sha256(content).hexdigest(),
            byte_length=len(content),
            media_type=artifact.media_type,
        )


def _max_bytes(artifact: SandboxExpectedArtifact) -> int:
    match artifact.kind:
        case "result":
            return _MAX_RESULT_JSON_BYTES
        case "summary":
            return _MAX_SUMMARY_MARKDOWN_BYTES
        case "chart" | "table":
            return _MAX_OPTIONAL_ARTIFACT_BYTES
