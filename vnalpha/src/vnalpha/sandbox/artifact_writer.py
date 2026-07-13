"""Descriptor-safe persistence for the canonical sandbox artifact set."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import TypedDict, final

from typing_extensions import override

from vnalpha.sandbox.artifact_finalization import SandboxArtifactManifestFinalizer
from vnalpha.sandbox.artifact_manifest import (
    SandboxArtifactManifest,
    SandboxArtifactManifestEntry,
)
from vnalpha.sandbox.contracts import SandboxOutputSchema
from vnalpha.sandbox.execution_evidence import SandboxExecutionEvidence
from vnalpha.sandbox.layout import SandboxArtifactLayout
from vnalpha.sandbox.models import SandboxJob
from vnalpha.sandbox.output_validation import SandboxOutputValidationResult
from vnalpha.sandbox.static_guard import SandboxGuardResult
from vnalpha.sandbox.storage import (
    SandboxArtifactNotFoundError,
    SandboxArtifactStorage,
)

_MAX_LIFECYCLE_BYTES = 65_536


class _ResourceLimitsPayload(TypedDict):
    cpu_millis: int
    memory_mb: int
    timeout_seconds: int


class _RequestPayload(TypedDict):
    code_digest: str
    correlation_id: str
    job_id: str
    network_enabled: bool
    purpose: str
    resource_limits: _ResourceLimitsPayload
    run_id: str


class _InputReferencesPayload(TypedDict):
    approved_read_paths: list[str]


@final
@dataclass(frozen=True, slots=True)
class SandboxArtifactCodeDigestError(ValueError):
    """Generated code does not match the job's durable digest."""

    expected: str
    actual: str

    @override
    def __str__(self) -> str:
        return "sandbox generated code does not match the persisted code digest"


@final
class SandboxArtifactWriterStateError(ValueError):
    """Output persistence was attempted before the canonical request artifacts exist."""

    @override
    def __str__(self) -> str:
        return "sandbox request artifacts must be persisted before output artifacts"


@final
class SandboxArtifactGuardStateError(ValueError):
    """Execution was attempted without matching persisted static-guard evidence."""

    @override
    def __str__(self) -> str:
        return "sandbox guard evidence must be persisted before execution artifacts"


@final
class SandboxArtifactGuardEvidenceMismatchError(ValueError):
    """A caller supplied a guard result different from persisted guard evidence."""

    @override
    def __str__(self) -> str:
        return "sandbox guard result does not match persisted guard evidence"


@final
@dataclass(frozen=True, slots=True)
class SandboxArtifactLayoutError(ValueError):
    """A caller attempted to redirect a fixed canonical sandbox artifact path."""

    layout: SandboxArtifactLayout

    @override
    def __str__(self) -> str:
        return "sandbox artifact writer requires the fixed canonical artifact layout"


@final
class SandboxArtifactWriter:
    """Write canonical sandbox artifacts through one descriptor-safe storage boundary."""

    def __init__(
        self,
        storage: SandboxArtifactStorage,
        layout: SandboxArtifactLayout | None = None,
    ) -> None:
        trusted_layout = SandboxArtifactLayout()
        if layout is not None and layout != trusted_layout:
            raise SandboxArtifactLayoutError(layout)
        self._storage = storage
        self._layout = trusted_layout
        self._host_entries: tuple[SandboxArtifactManifestEntry, ...] | None = None
        self._request_code_digest: str | None = None
        self._persisted_guard: SandboxGuardResult | None = None

    def persist_request(self, job: SandboxJob) -> None:
        """Atomically persist safe request metadata, code, and approved input references."""

        code_bytes = job.code.encode("utf-8")
        self.verify_code_digest(code_bytes, job.code_digest)
        request_bytes = _json_bytes(_request_payload(job))
        references_bytes = _json_bytes(_input_references_payload(job))
        self._storage.invalidate_file(self._layout.manifest.as_posix())
        self._host_entries = None
        self._request_code_digest = None
        self._persisted_guard = None
        self._storage.invalidate_file(self._layout.guard.as_posix())
        _ = self._storage.write_atomic_bytes(
            self._layout.request.as_posix(), request_bytes
        )
        _ = self._storage.write_atomic_bytes(
            self._layout.generated_code.as_posix(),
            code_bytes,
            mode=0o644,
        )
        _ = self._storage.write_atomic_bytes(
            self._layout.input_references.as_posix(), references_bytes
        )
        self._host_entries = (
            _entry(self._layout.request.as_posix(), request_bytes, "application/json"),
            _entry(self._layout.generated_code.as_posix(), code_bytes, "text/x-python"),
            _entry(
                self._layout.input_references.as_posix(),
                references_bytes,
                "application/json",
            ),
        )
        self._request_code_digest = job.code_digest

    def persist_guard(self, result: SandboxGuardResult) -> None:
        """Persist digest-bound guard evidence after the canonical request exists."""

        host_entries = self._host_entries
        request_code_digest = self._request_code_digest
        if host_entries is None or request_code_digest is None:
            raise SandboxArtifactWriterStateError()
        if result.code_digest != request_code_digest:
            raise SandboxArtifactCodeDigestError(
                request_code_digest, result.code_digest
            )
        guard_bytes = result.to_json_bytes()
        guard_path = self._layout.guard.as_posix()
        self._storage.invalidate_file(self._layout.manifest.as_posix())
        _ = self._storage.write_atomic_bytes(guard_path, guard_bytes)
        self._host_entries = (
            *(entry for entry in host_entries if entry.path != guard_path),
            _entry(guard_path, guard_bytes, "application/json"),
        )
        self._persisted_guard = result

    def persist_execution(self, evidence: SandboxExecutionEvidence) -> None:
        """Atomically persist execution metadata and exact bounded Docker streams."""

        host_entries = self._host_entries
        if host_entries is None:
            raise SandboxArtifactWriterStateError()
        if self._persisted_guard is None:
            raise SandboxArtifactGuardStateError()
        execution_bytes = evidence.to_json_bytes()
        stdout_path = self._layout.stdout.as_posix()
        stderr_path = self._layout.stderr.as_posix()
        execution_path = self._layout.execution.as_posix()
        self._storage.invalidate_file(self._layout.manifest.as_posix())
        _ = self._storage.write_atomic_bytes(stdout_path, evidence.stdout)
        _ = self._storage.write_atomic_bytes(stderr_path, evidence.stderr)
        _ = self._storage.write_atomic_bytes(execution_path, execution_bytes)
        self._host_entries = _replace_entries(
            host_entries,
            (
                _entry(stdout_path, evidence.stdout, "text/plain"),
                _entry(stderr_path, evidence.stderr, "text/plain"),
                _entry(execution_path, execution_bytes, "application/json"),
            ),
        )

    def persist_lifecycle_event(self, payload: dict[str, object]) -> None:
        host_entries = self._host_entries
        if host_entries is None:
            raise SandboxArtifactWriterStateError()
        lifecycle_path = self._layout.lifecycle.as_posix()
        try:
            existing = self._storage.read_bounded_regular_file(
                lifecycle_path, max_bytes=_MAX_LIFECYCLE_BYTES
            )
        except SandboxArtifactNotFoundError:
            existing = b""
        line = (
            json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            + "\n"
        ).encode("utf-8")
        content = existing + line
        self._storage.invalidate_file(self._layout.manifest.as_posix())
        _ = self._storage.write_atomic_bytes(lifecycle_path, content)
        self._host_entries = _replace_entries(
            host_entries,
            (_entry(lifecycle_path, content, "application/x-ndjson"),),
        )

    def persist_validation_and_manifest(
        self,
        validation: SandboxOutputValidationResult,
        output_schema: SandboxOutputSchema,
    ) -> SandboxArtifactManifest:
        """Persist host validation evidence, then finalize the sole trusted manifest."""

        host_entries = self._host_entries
        if host_entries is None:
            raise SandboxArtifactWriterStateError()
        manifest_path = self._layout.manifest.as_posix()
        validation_path = self._layout.validation.as_posix()
        validation_bytes = validation.evidence.to_json_bytes()
        self._storage.invalidate_file(manifest_path)
        _ = self._storage.write_atomic_bytes(validation_path, validation_bytes)
        final_host_entries = _replace_entries(
            host_entries,
            (_entry(validation_path, validation_bytes, "application/json"),),
        )
        manifest = SandboxArtifactManifestFinalizer(self._storage, output_schema).build(
            final_host_entries, validation
        )
        _ = self._storage.write_atomic_bytes(manifest_path, manifest.to_json_bytes())
        self._host_entries = final_host_entries
        return manifest

    def require_persisted_guard(self, result: SandboxGuardResult) -> None:
        """Require caller guard evidence to equal the immutable persisted decision."""

        if self._host_entries is None:
            raise SandboxArtifactWriterStateError()
        persisted_guard = self._persisted_guard
        if persisted_guard is None:
            raise SandboxArtifactGuardStateError()
        if persisted_guard != result:
            raise SandboxArtifactGuardEvidenceMismatchError()

    @staticmethod
    def verify_code_digest(code_bytes: bytes, persisted_digest: str) -> None:
        """Require generated bytes to match the code digest retained by the job record."""

        actual_digest = sha256(code_bytes).hexdigest()
        if actual_digest != persisted_digest:
            raise SandboxArtifactCodeDigestError(persisted_digest, actual_digest)


def _request_payload(job: SandboxJob) -> _RequestPayload:
    return {
        "code_digest": job.code_digest,
        "correlation_id": str(job.correlation_id),
        "job_id": str(job.job_id),
        "network_enabled": job.network_enabled,
        "purpose": job.purpose,
        "resource_limits": {
            "cpu_millis": job.resource_limits.cpu_millis,
            "memory_mb": job.resource_limits.memory_mb,
            "timeout_seconds": job.resource_limits.timeout_seconds,
        },
        "run_id": str(job.run_id),
    }


def _input_references_payload(job: SandboxJob) -> _InputReferencesPayload:
    return {"approved_read_paths": list(job.filesystem_policy.approved_read_paths)}


def _json_bytes(payload: _RequestPayload | _InputReferencesPayload) -> bytes:
    import json

    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _entry(path: str, content: bytes, media_type: str) -> SandboxArtifactManifestEntry:
    return SandboxArtifactManifestEntry(
        path=path,
        sha256=sha256(content).hexdigest(),
        byte_length=len(content),
        media_type=media_type,
    )


def _replace_entries(
    entries: tuple[SandboxArtifactManifestEntry, ...],
    replacements: tuple[SandboxArtifactManifestEntry, ...],
) -> tuple[SandboxArtifactManifestEntry, ...]:
    """Replace host entries by canonical path while preserving insertion order."""

    replacement_paths = frozenset(entry.path for entry in replacements)
    return (
        *(entry for entry in entries if entry.path not in replacement_paths),
        *replacements,
    )
