from __future__ import annotations

from pathlib import Path
from typing import ClassVar

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
