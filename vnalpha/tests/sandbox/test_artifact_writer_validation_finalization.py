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


def test_finalization_failure_inventories_only_observed_output_and_evidence(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())
        result = b"malformed result"
        _ = storage.write_atomic_bytes("output/result.json", result)
        _ = storage.write_atomic_bytes("output/undeclared.bin", b"untrusted")

        manifest = writer.persist_validation_and_manifest(
            _validation(
                _failed_evidence(),
                (_entry("output/result.json", result, "application/json"),),
            ),
            SandboxOutputSchema(),
        )

        paths = {entry.path for entry in manifest.entries}
        assert "validation.json" in paths
        assert "output/result.json" in paths
        assert "output/summary.md" not in paths
        assert "output/undeclared.bin" not in paths
        assert "manifest.json" not in paths


def test_finalization_excludes_fabricated_canonical_entry_outside_validation_inventory(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())
        result = b"validated"
        fabricated = b"fabricated"
        _ = storage.write_atomic_bytes("output/result.json", result)
        _ = storage.write_atomic_bytes("output/undeclared.bin", fabricated)

        manifest = writer.persist_validation_and_manifest(
            _validation(
                _failed_evidence(),
                (_entry("output/result.json", result, "application/json"),),
            ),
            SandboxOutputSchema(),
        )

        assert "output/undeclared.bin" not in {entry.path for entry in manifest.entries}


def test_finalization_recomputes_forged_declared_entry_from_storage(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())
        result = b"trusted result"
        _ = storage.write_atomic_bytes("output/result.json", result)
        forged = SandboxArtifactManifestEntry(
            path="output/result.json",
            sha256="0" * 64,
            byte_length=999,
            media_type="application/octet-stream",
        )
        evidence = SandboxOutputValidationEvidence(
            status=SandboxOutputValidationStatus.FAILED,
            failure_code=SandboxOutputValidationFailureCode.INVALID_SUMMARY,
            artifact_path="output/summary.md",
            detail="sandbox summary does not satisfy the output contract",
            validated_paths=("output/result.json",),
        )

        manifest = writer.persist_validation_and_manifest(
            _validation(evidence, (forged,)), SandboxOutputSchema()
        )

        assert {entry.path: entry for entry in manifest.entries}[
            "output/result.json"
        ] == _entry("output/result.json", result, "application/json")


def test_finalization_rejects_fabricated_path_outside_output_schema(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_finalization import (
        SandboxArtifactObservedEntryConflictError,
    )
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())
        fabricated = b"fabricated"
        _ = storage.write_atomic_bytes("output/undeclared.bin", fabricated)
        evidence = SandboxOutputValidationEvidence(
            status=SandboxOutputValidationStatus.FAILED,
            failure_code=SandboxOutputValidationFailureCode.INVALID_SUMMARY,
            artifact_path="output/summary.md",
            detail="sandbox summary does not satisfy the output contract",
            validated_paths=("output/undeclared.bin",),
        )

        with pytest.raises(SandboxArtifactObservedEntryConflictError):
            _ = writer.persist_validation_and_manifest(
                _validation(
                    evidence,
                    (_entry("output/undeclared.bin", fabricated, "text/plain"),),
                ),
                SandboxOutputSchema(),
            )

        assert not (storage.job_dir / "manifest.json").exists()


def test_finalization_rejects_duplicate_or_conflicting_observed_paths(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_finalization import (
        SandboxArtifactObservedEntryConflictError,
    )
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())
        result = b"result"
        _ = storage.write_atomic_bytes("output/result.json", result)
        observed = _entry("output/result.json", result, "application/json")
        duplicate_evidence = SandboxOutputValidationEvidence(
            status=SandboxOutputValidationStatus.FAILED,
            failure_code=SandboxOutputValidationFailureCode.INVALID_SUMMARY,
            artifact_path="output/summary.md",
            detail="sandbox summary does not satisfy the output contract",
            validated_paths=("output/result.json", "output/result.json"),
        )

        with pytest.raises(SandboxArtifactObservedEntryConflictError):
            _ = writer.persist_validation_and_manifest(
                _validation(duplicate_evidence, (observed, observed)),
                SandboxOutputSchema(),
            )
        with pytest.raises(SandboxArtifactObservedEntryConflictError):
            _ = writer.persist_validation_and_manifest(
                _validation(
                    SandboxOutputValidationEvidence(
                        status=SandboxOutputValidationStatus.FAILED,
                        failure_code=SandboxOutputValidationFailureCode.INVALID_SUMMARY,
                        artifact_path="output/summary.md",
                        detail="sandbox summary does not satisfy the output contract",
                        validated_paths=("request.json",),
                    ),
                    (_entry("request.json", b"untrusted", "application/json"),),
                ),
                SandboxOutputSchema(),
            )

        assert not (storage.job_dir / "manifest.json").exists()


@pytest.mark.parametrize("failed_path", ["validation.json", "manifest.json"])
def test_finalization_leaves_no_manifest_when_persistence_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_path: str
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())
        result = b"result"
        _ = storage.write_atomic_bytes("output/result.json", result)
        observed = _entry("output/result.json", result, "application/json")
        original_write = storage.write_atomic_bytes

        def fail_write(path: str, content: bytes) -> Path:
            if path == failed_path:
                raise SandboxArtifactPathError(path)
            return original_write(path, content)

        monkeypatch.setattr(storage, "write_atomic_bytes", fail_write)

        with pytest.raises(SandboxArtifactPathError):
            _ = writer.persist_validation_and_manifest(
                _validation(_failed_evidence(), (observed,)), SandboxOutputSchema()
            )

        assert not (storage.job_dir / "manifest.json").exists()
