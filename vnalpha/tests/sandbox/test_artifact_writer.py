from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.contracts import ApprovedReadPath, SandboxFilesystemPolicy
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.storage import SandboxArtifactStorage


class _ResourceLimitsPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    cpu_millis: int
    memory_mb: int
    timeout_seconds: int


class _RequestPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    code_digest: str
    correlation_id: str
    job_id: str
    network_enabled: bool
    purpose: str
    resource_limits: _ResourceLimitsPayload
    run_id: str


class _InputReferencesPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    approved_read_paths: tuple[str, ...]


def _job() -> SandboxJob:
    return SandboxJob(
        job_id=SandboxJobId("job-001"),
        run_id=SandboxRunId("run-001"),
        purpose="evaluate a reference dataset",
        code="print('generated result')\n",
        correlation_id=SandboxCorrelationId("correlation-001"),
        resource_limits=SandboxResourceLimits(
            cpu_millis=100, memory_mb=64, timeout_seconds=30
        ),
        network_enabled=False,
        filesystem_policy=SandboxFilesystemPolicy(
            approved_read_paths=(ApprovedReadPath("inputs/reference.csv"),)
        ),
    )


def _storage(tmp_path: Path) -> SandboxArtifactStorage:
    return SandboxArtifactStorage(
        RunContext(run_id="run-001", surface="test", actor="pytest", log_root=tmp_path),
        SandboxJobId("job-001"),
    )


def test_persist_request_writes_safe_metadata_code_and_approved_references(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    job = _job()
    with _storage(tmp_path) as storage:
        SandboxArtifactWriter(storage).persist_request(job)

        request = _RequestPayload.model_validate_json(
            (storage.job_dir / "request.json").read_bytes()
        )
        assert request.code_digest == job.code_digest
        assert request.correlation_id == "correlation-001"
        assert request.job_id == "job-001"
        assert not request.network_enabled
        assert request.purpose == "evaluate a reference dataset"
        assert request.resource_limits == _ResourceLimitsPayload(
            cpu_millis=100, memory_mb=64, timeout_seconds=30
        )
        assert request.run_id == "run-001"
        assert (storage.job_dir / "generated_code.py").read_bytes() == job.code.encode()
        references = _InputReferencesPayload.model_validate_json(
            (storage.job_dir / "inputs/references.json").read_bytes()
        )
        assert references.approved_read_paths == ("inputs/reference.csv",)
        assert "secret" not in (storage.job_dir / "request.json").read_text().lower()


def test_manifest_rejects_duplicate_and_unsafe_paths() -> None:
    from vnalpha.sandbox.artifact_manifest import (
        SandboxArtifactManifest,
        SandboxArtifactManifestEntry,
        SandboxArtifactManifestError,
    )

    entry = SandboxArtifactManifestEntry(
        path="request.json",
        sha256="0" * 64,
        byte_length=1,
        media_type="application/json",
    )

    with pytest.raises(SandboxArtifactManifestError):
        _ = SandboxArtifactManifest(entries=(entry, entry))
    with pytest.raises(SandboxArtifactManifestError):
        _ = SandboxArtifactManifestEntry(
            path="../request.json",
            sha256="0" * 64,
            byte_length=1,
            media_type="application/json",
        )
    with pytest.raises(SandboxArtifactManifestError):
        _ = SandboxArtifactManifestEntry(
            path="output/result.json",
            sha256="malformed",
            byte_length=1,
            media_type="application/json",
        )


def test_persist_request_rejects_code_digest_mismatch_before_manifest(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import (
        SandboxArtifactCodeDigestError,
        SandboxArtifactWriter,
    )

    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        with pytest.raises(SandboxArtifactCodeDigestError):
            writer.verify_code_digest(b"different", _job().code_digest)

        assert not (storage.job_dir / "manifest.json").exists()


def test_writer_rejects_tampered_canonical_layout_before_writing_artifacts(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
    from vnalpha.sandbox.layout import SandboxArtifactLayout

    tampered_layout = SandboxArtifactLayout(
        request=PurePosixPath("redirect/request.json"),
        generated_code=PurePosixPath("redirect/generated_code.py"),
        result=PurePosixPath("redirect/output/result.json"),
        summary=PurePosixPath("redirect/output/summary.md"),
        manifest=PurePosixPath("redirect/manifest.json"),
    )
    with _storage(tmp_path) as storage:
        with pytest.raises(ValueError):
            _ = SandboxArtifactWriter(storage, tampered_layout)

        assert not tuple(storage.job_dir.iterdir())
