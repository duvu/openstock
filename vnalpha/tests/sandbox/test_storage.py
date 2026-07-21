from __future__ import annotations

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
