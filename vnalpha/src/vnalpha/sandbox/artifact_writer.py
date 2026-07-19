"""Descriptor-safe persistence for the canonical sandbox artifact set."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import TypedDict, final, override

from vnalpha.sandbox.artifact_manifest import (
    SandboxArtifactManifest,
    SandboxArtifactManifestEntry,
)
from vnalpha.sandbox.layout import SandboxArtifactLayout
from vnalpha.sandbox.models import SandboxJob
from vnalpha.sandbox.static_guard import SandboxGuardResult
from vnalpha.sandbox.storage import SandboxArtifactStorage


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
        self._request_entries: tuple[SandboxArtifactManifestEntry, ...] | None = None
        self._request_code_digest: str | None = None

    def persist_request(self, job: SandboxJob) -> None:
        """Atomically persist safe request metadata, code, and approved input references."""

        code_bytes = job.code.encode("utf-8")
        self.verify_code_digest(code_bytes, job.code_digest)
        request_bytes = _json_bytes(_request_payload(job))
        references_bytes = _json_bytes(_input_references_payload(job))
        self._storage.invalidate_file(self._layout.manifest.as_posix())
        self._request_entries = None
        self._request_code_digest = None
        self._storage.invalidate_file(self._layout.guard.as_posix())
        _ = self._storage.write_atomic_bytes(
            self._layout.request.as_posix(), request_bytes
        )
        _ = self._storage.write_atomic_bytes(
            self._layout.generated_code.as_posix(), code_bytes
        )
        _ = self._storage.write_atomic_bytes(
            self._layout.input_references.as_posix(), references_bytes
        )
        self._request_entries = (
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

        request_entries = self._request_entries
        request_code_digest = self._request_code_digest
        if request_entries is None or request_code_digest is None:
            raise SandboxArtifactWriterStateError()
        if result.code_digest != request_code_digest:
            raise SandboxArtifactCodeDigestError(
                request_code_digest, result.code_digest
            )
        guard_bytes = result.to_json_bytes()
        guard_path = self._layout.guard.as_posix()
        self._storage.invalidate_file(self._layout.manifest.as_posix())
        _ = self._storage.write_atomic_bytes(guard_path, guard_bytes)
        self._request_entries = (
            *(entry for entry in request_entries if entry.path != guard_path),
            _entry(guard_path, guard_bytes, "application/json"),
        )

    def persist_outputs(
        self, result_json: bytes, summary_markdown: str
    ) -> SandboxArtifactManifest:
        """Atomically persist raw outputs, then write their deterministic manifest."""

        request_entries = self._request_entries
        if request_entries is None:
            raise SandboxArtifactWriterStateError()
        summary_bytes = summary_markdown.encode("utf-8")
        self._storage.invalidate_file(self._layout.manifest.as_posix())
        _ = self._storage.write_atomic_bytes(
            self._layout.result.as_posix(), result_json
        )
        _ = self._storage.write_atomic_bytes(
            self._layout.summary.as_posix(), summary_bytes
        )
        manifest = SandboxArtifactManifest(
            entries=(
                *request_entries,
                _entry(self._layout.result.as_posix(), result_json, "application/json"),
                _entry(self._layout.summary.as_posix(), summary_bytes, "text/markdown"),
            )
        )
        _ = self._storage.write_atomic_bytes(
            self._layout.manifest.as_posix(), manifest.to_json_bytes()
        )
        return manifest

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
