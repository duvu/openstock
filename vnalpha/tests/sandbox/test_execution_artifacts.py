from __future__ import annotations

from pathlib import Path

import pytest

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.contracts import SandboxFilesystemPolicy
from vnalpha.sandbox.docker_runner import DockerExecutionResult
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.static_guard import SandboxStaticGuard
from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage


def _job() -> SandboxJob:
    return SandboxJob(
        job_id=SandboxJobId("job-001"),
        run_id=SandboxRunId("run-001"),
        purpose="evaluate a reference dataset",
        code="1 + 1\n",
        correlation_id=SandboxCorrelationId("correlation-001"),
        resource_limits=SandboxResourceLimits(
            cpu_millis=100, memory_mb=64, timeout_seconds=30
        ),
        network_enabled=False,
        filesystem_policy=SandboxFilesystemPolicy(),
    )


def _storage(tmp_path: Path) -> SandboxArtifactStorage:
    return SandboxArtifactStorage(
        RunContext(run_id="run-001", surface="test", actor="pytest", log_root=tmp_path),
        SandboxJobId("job-001"),
    )


def test_persist_execution_writes_canonical_metadata_and_exact_stream_bytes(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
    from vnalpha.sandbox.execution_evidence import (
        SandboxExecutionEvidence,
        SandboxExecutionStatus,
    )

    # Given
    result = DockerExecutionResult(
        return_code=0,
        stdout=b"stdout\xff",
        stderr=b"stderr\x00",
        stdout_truncated=True,
        stderr_truncated=False,
    )
    evidence = SandboxExecutionEvidence.from_result(
        SandboxExecutionStatus.SUCCEEDED, result
    )
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        job = _job()
        writer.persist_request(job)
        writer.persist_guard(SandboxStaticGuard.evaluate(job.code))
        _ = storage.write_atomic_bytes("manifest.json", b"existing-manifest")

        # When
        writer.persist_execution(evidence)

        # Then
        assert (storage.job_dir / "execution.json").read_bytes() == (
            b"{\n"
            b'  "cleanup_succeeded": null,\n'
            b'  "detail": "",\n'
            b'  "failure_code": null,\n'
            b'  "return_code": 0,\n'
            b'  "schema_version": 1,\n'
            b'  "status": "succeeded",\n'
            b'  "stderr_truncated": false,\n'
            b'  "stdout_truncated": true\n'
            b"}\n"
        )
        assert (storage.job_dir / "output/stdout.txt").read_bytes() == b"stdout\xff"
        assert (storage.job_dir / "output/stderr.txt").read_bytes() == b"stderr\x00"
        assert not (storage.job_dir / "manifest.json").exists()


def test_persist_execution_removes_manifest_before_a_failed_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
    from vnalpha.sandbox.execution_evidence import (
        SandboxExecutionEvidence,
        SandboxExecutionStatus,
    )

    evidence = SandboxExecutionEvidence.from_result(
        SandboxExecutionStatus.FAILED,
        DockerExecutionResult(return_code=1, stdout=b"retry", stderr=b"failed"),
    )
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        job = _job()
        writer.persist_request(job)
        writer.persist_guard(SandboxStaticGuard.evaluate(job.code))
        _ = storage.write_atomic_bytes("manifest.json", b"stale-manifest")
        write_atomic_bytes = storage.write_atomic_bytes

        def fail_stdout(path: str, content: bytes) -> Path:
            if path == "output/stdout.txt":
                raise SandboxArtifactPathError(path)
            return write_atomic_bytes(path, content)

        monkeypatch.setattr(storage, "write_atomic_bytes", fail_stdout)

        with pytest.raises(SandboxArtifactPathError):
            writer.persist_execution(evidence)

        assert not (storage.job_dir / "manifest.json").exists()


def test_persist_execution_requires_request_artifacts(tmp_path: Path) -> None:
    from vnalpha.sandbox.artifact_writer import (
        SandboxArtifactWriter,
        SandboxArtifactWriterStateError,
    )
    from vnalpha.sandbox.execution_evidence import (
        SandboxExecutionEvidence,
        SandboxExecutionStatus,
    )

    # Given
    evidence = SandboxExecutionEvidence.from_result(
        SandboxExecutionStatus.FAILED,
        DockerExecutionResult(return_code=1, stdout=b"", stderr=b"failure"),
    )
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)

        # When / Then
        with pytest.raises(SandboxArtifactWriterStateError):
            writer.persist_execution(evidence)
        assert not (storage.job_dir / "execution.json").exists()
