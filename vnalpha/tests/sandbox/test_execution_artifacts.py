from __future__ import annotations

import json
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
            b'  "preflight": null,\n'
            b'  "return_code": 0,\n'
            b'  "schema_version": 2,\n'
            b'  "security_controls": null,\n'
            b'  "status": "succeeded",\n'
            b'  "stderr_truncated": false,\n'
            b'  "stdout_truncated": true\n'
            b"}\n"
        )
        assert (storage.job_dir / "output/stdout.txt").read_bytes() == b"stdout\xff"
        assert (storage.job_dir / "output/stderr.txt").read_bytes() == b"stderr\x00"
        assert not (storage.job_dir / "manifest.json").exists()


def test_execution_evidence_records_preflight_and_effective_security_controls(
    tmp_path: Path,
) -> None:
    # Given: one successful preflight and an exact hardened Docker request
    from vnalpha.sandbox.docker_policy import DockerExecutionRequest
    from vnalpha.sandbox.docker_runner import DockerPreflightResult
    from vnalpha.sandbox.execution_evidence import (
        SandboxExecutionEvidence,
        SandboxExecutionStatus,
    )

    code_path = tmp_path / "generated.py"
    code_path.write_text("result = 2\n", encoding="utf-8")
    output_path = tmp_path / "output"
    output_path.mkdir()
    job = _job()
    request = DockerExecutionRequest(
        image=f"registry.example/openstock/sandbox@sha256:{'a' * 64}",
        code_path=code_path,
        input_paths=(),
        output_path=output_path,
        resource_limits=job.resource_limits,
    )
    result = DockerExecutionResult(
        return_code=0,
        stdout=b"",
        stderr=b"",
        preflight=DockerPreflightResult(
            docker_available=True,
            linux_supported=True,
            detail="ready",
            server_os="linux",
        ),
    )

    # When: execution evidence is serialized
    evidence = SandboxExecutionEvidence.from_result(
        SandboxExecutionStatus.SUCCEEDED, result, request
    )
    payload = json.loads(evidence.to_json_bytes())

    # Then: positive preflight and controls are durable without host paths
    assert payload["preflight"] == {
        "detail": "ready",
        "docker_available": True,
        "failure_code": None,
        "linux_supported": True,
        "server_os": "linux",
    }
    controls = payload["security_controls"]
    assert controls["image_digest"] == f"sha256:{'a' * 64}"
    assert controls["network"] == "none"
    assert controls["root_read_only"] is True
    assert controls["capabilities_dropped"] == "ALL"
    assert controls["no_new_privileges"] is True
    assert controls["environment_forwarded"] is False
    assert controls["input_mount_count"] == 0
    assert str(tmp_path) not in evidence.to_json_bytes().decode("utf-8")


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
