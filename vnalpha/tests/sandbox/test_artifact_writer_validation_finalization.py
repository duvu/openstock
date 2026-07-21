from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.artifact_manifest import SandboxArtifactManifestEntry
from vnalpha.sandbox.contracts import SandboxFilesystemPolicy, SandboxOutputSchema
from vnalpha.sandbox.docker_runner import DockerExecutionResult
from vnalpha.sandbox.execution_evidence import (
    SandboxExecutionEvidence,
    SandboxExecutionStatus,
)
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.output_validation import (
    SandboxOutputValidationEvidence,
    SandboxOutputValidationFailureCode,
    SandboxOutputValidationResult,
    SandboxOutputValidationStatus,
)
from vnalpha.sandbox.static_guard import SandboxStaticGuard
from vnalpha.sandbox.storage import SandboxArtifactStorage


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


def _entry(path: str, content: bytes, media_type: str) -> SandboxArtifactManifestEntry:
    return SandboxArtifactManifestEntry(
        path=path,
        sha256=hashlib.sha256(content).hexdigest(),
        byte_length=len(content),
        media_type=media_type,
    )


def _success_evidence() -> SandboxOutputValidationEvidence:
    return SandboxOutputValidationEvidence(
        status=SandboxOutputValidationStatus.SUCCEEDED,
        failure_code=None,
        artifact_path=None,
        detail="sandbox outputs satisfy the expected artifact contract",
        validated_paths=("output/result.json", "output/summary.md"),
    )


def _failed_evidence() -> SandboxOutputValidationEvidence:
    return SandboxOutputValidationEvidence(
        status=SandboxOutputValidationStatus.FAILED,
        failure_code=SandboxOutputValidationFailureCode.INVALID_SUMMARY,
        artifact_path="output/summary.md",
        detail="sandbox summary does not satisfy the output contract",
        validated_paths=("output/result.json",),
    )


def _validation(
    evidence: SandboxOutputValidationEvidence,
    inventory: tuple[SandboxArtifactManifestEntry, ...],
) -> SandboxOutputValidationResult:
    return SandboxOutputValidationResult(
        evidence=evidence,
        result=None,
        inventory=inventory,
    )


def test_finalization_tracks_execution_and_writes_validation_before_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        job = _job()
        writer.persist_request(job)
        writer.persist_guard(SandboxStaticGuard.evaluate(job.code))
        execution = SandboxExecutionEvidence.from_result(
            SandboxExecutionStatus.SUCCEEDED,
            DockerExecutionResult(
                return_code=0, stdout=b"stdout\xff", stderr=b"stderr\x00"
            ),
        )
        writer.persist_execution(execution)
        result = b'{"artifacts":[],"schema_version":1,"summary":"done"}\n'
        summary = b"# done\n"
        _ = storage.write_atomic_bytes("output/result.json", result)
        _ = storage.write_atomic_bytes("output/summary.md", summary)
        _ = storage.write_atomic_bytes("manifest.json", b"container-authored")
        written_paths: list[str] = []
        write_atomic_bytes = storage.write_atomic_bytes

        def record_write(path: str, content: bytes) -> Path:
            written_paths.append(path)
            return write_atomic_bytes(path, content)

        monkeypatch.setattr(storage, "write_atomic_bytes", record_write)

        manifest = writer.persist_validation_and_manifest(
            _validation(
                _success_evidence(),
                (
                    _entry("output/result.json", result, "application/json"),
                    _entry("output/summary.md", summary, "text/markdown"),
                ),
            ),
            SandboxOutputSchema(),
        )

        assert written_paths == ["validation.json", "manifest.json"]
        assert (storage.job_dir / "output/stdout.txt").read_bytes() == b"stdout\xff"
        assert (storage.job_dir / "output/stderr.txt").read_bytes() == b"stderr\x00"
        assert (storage.job_dir / "manifest.json").read_bytes() != b"container-authored"
        assert [entry.path for entry in manifest.entries] == [
            "request.json",
            "generated_code.py",
            "inputs/references.json",
            "guard.json",
            "output/stdout.txt",
            "output/stderr.txt",
            "execution.json",
            "validation.json",
            "output/result.json",
            "output/summary.md",
        ]
        assert (
            storage.job_dir / "manifest.json"
        ).read_bytes() == manifest.to_json_bytes()
        entries = {entry.path: entry for entry in manifest.entries}
        assert entries["execution.json"] == _entry(
            "execution.json", execution.to_json_bytes(), "application/json"
        )
        assert entries["output/stdout.txt"] == _entry(
            "output/stdout.txt", b"stdout\xff", "text/plain"
        )
