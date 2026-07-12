from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.artifact_manifest import SandboxArtifactManifest
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.contracts import SandboxFilesystemPolicy, SandboxOutputSchema
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.output_validation import SandboxOutputValidator
from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage


def _job() -> SandboxJob:
    return SandboxJob(
        job_id=SandboxJobId("job-001"),
        run_id=SandboxRunId("run-001"),
        purpose="evaluate a reference dataset",
        code="import math\nresult = math.sqrt(9)\n",
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


def _finalize(
    writer: SandboxArtifactWriter, storage: SandboxArtifactStorage
) -> SandboxArtifactManifest:
    _ = storage.write_atomic_bytes(
        "output/result.json",
        b'{"artifacts":[],"schema_version":1,"summary":"done"}\n',
    )
    _ = storage.write_atomic_bytes("output/summary.md", b"# done\n")
    validation = SandboxOutputValidator(storage).validate(SandboxOutputSchema())
    return writer.persist_validation_and_manifest(validation, SandboxOutputSchema())


def test_persist_guard_requires_persisted_request_and_matching_digest(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import (
        SandboxArtifactWriter,
        SandboxArtifactWriterStateError,
    )
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    # Given
    job = _job()
    evidence = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)

        # When / Then
        with pytest.raises(SandboxArtifactWriterStateError):
            writer.persist_guard(evidence)
        assert not (storage.job_dir / "guard.json").exists()


def test_persist_guard_writes_canonical_evidence_and_adds_later_manifest_entry(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    # Given
    job = _job()
    evidence = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)

        # When
        writer.persist_guard(evidence)
        manifest = _finalize(writer, storage)

        # Then
        guard_bytes = (storage.job_dir / "guard.json").read_bytes()
        assert guard_bytes == evidence.to_json_bytes()
        assert guard_bytes.endswith(b"\n")
        assert "generated_code.py" in {entry.path for entry in manifest.entries}
        assert "guard.json" in {entry.path for entry in manifest.entries}


def test_repeated_guard_persistence_keeps_one_manifest_entry(tmp_path: Path) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    # Given
    job = _job()
    evidence = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)

        # When
        writer.persist_guard(evidence)
        writer.persist_guard(evidence)
        manifest = _finalize(writer, storage)

        # Then
        assert [entry.path for entry in manifest.entries].count("guard.json") == 1


def test_guard_replacement_invalidates_a_committed_output_manifest(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    # Given
    job = _job()
    evidence = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(evidence)
        _ = _finalize(writer, storage)
        manifest_path = storage.job_dir / "manifest.json"
        assert manifest_path.exists()

        # When
        writer.persist_guard(evidence)

        # Then
        assert not manifest_path.exists()


def test_request_retry_clears_stale_guard_and_committed_manifest(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    # Given
    job = _job()
    replacement_job = replace(job, code="sqrt(4)")
    evidence = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(evidence)
        _ = _finalize(writer, storage)

        # When
        writer.persist_request(replacement_job)

        # Then
        assert not (storage.job_dir / "manifest.json").exists()
        assert not (storage.job_dir / "guard.json").exists()
        assert (storage.job_dir / "generated_code.py").read_text() == "sqrt(4)"


def test_partial_request_retry_clears_retained_writer_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vnalpha.sandbox.artifact_writer import (
        SandboxArtifactWriter,
        SandboxArtifactWriterStateError,
    )

    # Given
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())
        original_replace = os.replace

        def fail_references_replacement(
            source: str,
            destination: str,
            *,
            src_dir_fd: int | None = None,
            dst_dir_fd: int | None = None,
        ) -> None:
            if destination == "references.json":
                raise OSError("references replacement failed")
            original_replace(
                source,
                destination,
                src_dir_fd=src_dir_fd,
                dst_dir_fd=dst_dir_fd,
            )

        monkeypatch.setattr(os, "replace", fail_references_replacement)

        # When
        with pytest.raises(SandboxArtifactPathError):
            writer.persist_request(replace(_job(), code="sqrt(4)"))

        # Then
        with pytest.raises(SandboxArtifactWriterStateError):
            _ = _finalize(writer, storage)


def test_symlinked_guard_retry_clears_retained_writer_state(tmp_path: Path) -> None:
    from vnalpha.sandbox.artifact_writer import (
        SandboxArtifactWriter,
        SandboxArtifactWriterStateError,
    )

    # Given
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())
        (storage.job_dir / "guard.json").symlink_to(tmp_path / "outside-guard.json")

        # When
        with pytest.raises(SandboxArtifactPathError):
            writer.persist_request(replace(_job(), code="sqrt(4)"))

        # Then
        with pytest.raises(SandboxArtifactWriterStateError):
            _ = _finalize(writer, storage)


def test_persist_guard_rejects_evidence_for_different_code(tmp_path: Path) -> None:
    from vnalpha.sandbox.artifact_writer import (
        SandboxArtifactCodeDigestError,
        SandboxArtifactWriter,
    )
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    # Given
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())

        # When / Then
        with pytest.raises(SandboxArtifactCodeDigestError):
            writer.persist_guard(SandboxStaticGuard.evaluate("result = 1\n"))
        assert not (storage.job_dir / "guard.json").exists()


def test_outputs_remain_valid_when_guard_evidence_is_not_persisted(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter

    # Given
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(_job())

        # When
        manifest = _finalize(writer, storage)

        # Then
        assert "guard.json" not in {entry.path for entry in manifest.entries}
