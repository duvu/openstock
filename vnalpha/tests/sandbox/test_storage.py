from __future__ import annotations

import os
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
