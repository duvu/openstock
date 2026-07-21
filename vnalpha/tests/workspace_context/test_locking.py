from __future__ import annotations

import json
from pathlib import Path

import pytest

from vnalpha.workspace_context.locking import (
    WorkspaceLockContentionError,
    workspace_transaction,
)
from vnalpha.workspace_context.mutations import record_input
from vnalpha.workspace_context.storage import (
    load_workspace_state,
)


def _record_input_worker(root: str, workspace_id: str, barrier) -> None:
    root_path = Path(root)
    workspace = load_workspace_state(root=root_path, workspace_id=workspace_id)
    barrier.wait()
    record_input(workspace, "concurrent input", "worker", root=root_path)


def test_workspace_transaction_records_owner_metadata_and_releases(tmp_path) -> None:
    with workspace_transaction("ws-lock", root=tmp_path) as paths:
        metadata = json.loads(paths.lock_path.read_text(encoding="utf-8"))

        assert metadata["workspace_id"] == "ws-lock"
        assert metadata["owner_token"]
        assert metadata["pid"] > 0
        assert metadata["hostname"]
        assert metadata["created_at"]
        with pytest.raises(WorkspaceLockContentionError):
            with workspace_transaction("ws-lock", root=tmp_path, timeout_seconds=0):
                pass

    assert paths.lock_path.exists() is False
