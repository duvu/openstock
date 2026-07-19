from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.models import SandboxJobId


def test_storage_creates_only_canonical_job_directory_and_contains_artifacts(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        artifact_path = storage.path_for("outputs/result.json")

        assert storage.job_dir == run_context.run_dir / "sandbox" / "job-001"
        assert storage.job_dir.is_dir()
        assert artifact_path == storage.job_dir / "outputs" / "result.json"
        assert not artifact_path.parent.exists()

        with pytest.raises(SandboxArtifactPathError):
            _ = storage.path_for("/tmp/escaped.txt")
        with pytest.raises(SandboxArtifactPathError):
            _ = storage.path_for("../escaped.txt")


def test_storage_rejects_traversal_job_id_before_creating_outside_sandbox(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    escaped_dir = run_context.run_dir / "outside"

    with pytest.raises(SandboxArtifactPathError):
        _ = SandboxArtifactStorage(run_context, SandboxJobId("../outside"))

    assert not escaped_dir.exists()


@pytest.mark.parametrize(
    "job_id",
    ("", ".", "/absolute", "nested/job", "nested\\job"),
)
def test_storage_rejects_non_component_job_ids(tmp_path: Path, job_id: str) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )

    with pytest.raises(SandboxArtifactPathError):
        _ = SandboxArtifactStorage(run_context, SandboxJobId(job_id))


def test_storage_rejects_symlinked_job_id(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    sandbox_dir = run_context.run_dir / "sandbox"
    sandbox_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (sandbox_dir / "linked").symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(SandboxArtifactPathError):
        _ = SandboxArtifactStorage(run_context, SandboxJobId("linked"))


def test_storage_refuses_sandbox_root_replaced_during_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    sandbox_dir = run_context.run_dir / "sandbox"
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    original_mkdir = os.mkdir

    def replace_sandbox_dir(
        path: str | Path, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> None:
        if path == sandbox_dir or (path == "sandbox" and dir_fd is not None):
            sandbox_dir.symlink_to(outside_dir, target_is_directory=True)
        _ = original_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "mkdir", replace_sandbox_dir)

    with pytest.raises(SandboxArtifactPathError):
        _ = SandboxArtifactStorage(run_context, SandboxJobId("job-001"))

    assert not (outside_dir / "job-001").exists()


def test_secure_write_refuses_component_replaced_by_symlink(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        artifact_dir = storage.job_dir / "artifacts"
        artifact_dir.mkdir()
        _ = storage.path_for("artifacts/result.txt")
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        artifact_dir.rmdir()
        artifact_dir.symlink_to(outside_dir, target_is_directory=True)

        with pytest.raises(SandboxArtifactPathError):
            _ = storage.write_bytes("artifacts/result.txt", b"must not escape")

        assert not (outside_dir / "result.txt").exists()


def test_secure_write_creates_contained_artifact(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        artifact_path = storage.write_bytes("artifacts/result.txt", b"contained")

        assert artifact_path == storage.job_dir / "artifacts" / "result.txt"
        assert artifact_path.read_bytes() == b"contained"


def test_ensure_directory_creates_contained_nested_directory(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        directory = storage.ensure_directory("output/nested")

        assert directory == storage.job_dir / "output" / "nested"
        assert directory.is_dir()


@pytest.mark.parametrize("raw_path", ("/tmp/escaped", "../escaped"))
def test_ensure_directory_rejects_unsafe_paths(tmp_path: Path, raw_path: str) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        with pytest.raises(SandboxArtifactPathError):
            _ = storage.ensure_directory(raw_path)


def test_ensure_directory_refuses_symlinked_component(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        (storage.job_dir / "output").symlink_to(outside_dir, target_is_directory=True)

        with pytest.raises(SandboxArtifactPathError):
            _ = storage.ensure_directory("output/nested")

        assert not (outside_dir / "nested").exists()


def test_atomic_write_replaces_existing_artifact_without_exposing_partial_content(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        _ = storage.write_atomic_bytes("output/result.json", b"first complete value")
        artifact_path = storage.write_atomic_bytes("output/result.json", b"replacement")

        assert artifact_path.read_bytes() == b"replacement"
        assert stat.S_IMODE(artifact_path.stat().st_mode) == 0o600
        assert not tuple(artifact_path.parent.glob(".sandbox-artifact-*"))


def test_atomic_write_cleans_temporary_artifact_and_preserves_destination_after_write_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        artifact_path = storage.write_atomic_bytes("output/result.json", b"original")

        def fail_write(_fd: int, _content: bytes) -> int:
            raise OSError("disk write failed")

        monkeypatch.setattr(os, "write", fail_write)

        with pytest.raises(SandboxArtifactPathError):
            _ = storage.write_atomic_bytes("output/result.json", b"replacement")

        assert artifact_path.read_bytes() == b"original"
        assert not tuple(artifact_path.parent.glob(".sandbox-artifact-*"))


def test_atomic_write_refuses_symlinked_destination_component(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (storage.job_dir / "output").symlink_to(outside_dir, target_is_directory=True)

        with pytest.raises(SandboxArtifactPathError):
            _ = storage.write_atomic_bytes("output/result.json", b"must not escape")

        assert not (outside_dir / "result.json").exists()


def test_atomic_write_rejects_unsafe_paths_and_closed_storage(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    storage = SandboxArtifactStorage(run_context, SandboxJobId("job-001"))
    with pytest.raises(SandboxArtifactPathError):
        _ = storage.write_atomic_bytes("/tmp/escaped", b"unsafe")
    with pytest.raises(SandboxArtifactPathError):
        _ = storage.write_atomic_bytes("../escaped", b"unsafe")
    storage.close()

    with pytest.raises(SandboxArtifactPathError):
        _ = storage.write_atomic_bytes("output/result.json", b"closed")


def test_invalidate_removes_contained_artifact_and_rejects_unsafe_or_closed_storage(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    storage = SandboxArtifactStorage(run_context, SandboxJobId("job-001"))
    artifact_path = storage.write_atomic_bytes("manifest.json", b"committed")
    storage.invalidate_file("manifest.json")

    assert not artifact_path.exists()
    with pytest.raises(SandboxArtifactPathError):
        storage.invalidate_file("../manifest.json")
    storage.close()

    with pytest.raises(SandboxArtifactPathError):
        storage.invalidate_file("manifest.json")


def test_invalidate_rejects_symlinked_artifact(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    outside_path = tmp_path / "outside"
    _ = outside_path.write_bytes(b"outside")
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        manifest_path = storage.job_dir / "manifest.json"
        manifest_path.symlink_to(outside_path)

        with pytest.raises(SandboxArtifactPathError):
            storage.invalidate_file("manifest.json")

        assert manifest_path.is_symlink()


def test_storage_context_manager_closes_descriptor_idempotently(tmp_path: Path) -> None:
    from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    with SandboxArtifactStorage(run_context, SandboxJobId("job-001")) as storage:
        _ = storage.write_bytes("result.txt", b"contained")
    storage.close()
    with pytest.raises(SandboxArtifactPathError):
        _ = storage.write_bytes("result.txt", b"closed")
