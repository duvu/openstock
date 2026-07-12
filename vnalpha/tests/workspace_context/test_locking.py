from __future__ import annotations

import json
import multiprocessing
import os
import time
from pathlib import Path

import pytest

from vnalpha.workspace_context.lifecycle import create_workspace
from vnalpha.workspace_context.locking import (
    WorkspaceLockContentionError,
    workspace_transaction,
)
from vnalpha.workspace_context.mutations import record_input
from vnalpha.workspace_context.storage import (
    ensure_workspace_layout,
    load_workspace_state,
    release_workspace_lock,
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


def test_release_does_not_delete_lock_for_a_different_owner(tmp_path) -> None:
    with workspace_transaction("ws-owner", root=tmp_path) as paths:
        release_workspace_lock(
            root=tmp_path,
            workspace_id="ws-owner",
            owner_token="different-owner",
        )

        assert paths.lock_path.exists()


def test_stale_lock_is_replaced_without_releasing_a_new_owner(tmp_path) -> None:
    paths = ensure_workspace_layout(root=tmp_path, workspace_id="ws-stale")
    paths.lock_path.write_text(
        json.dumps(
            {
                "workspace_id": "ws-stale",
                "owner_token": "old-owner",
                "pid": 1,
                "hostname": "old-host",
                "created_at": "2020-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    old_time = time.time() - 3600
    os.utime(paths.lock_path, (old_time, old_time))

    with workspace_transaction("ws-stale", root=tmp_path, stale_seconds=1):
        metadata = json.loads(paths.lock_path.read_text(encoding="utf-8"))
        assert metadata["owner_token"] != "old-owner"


def test_concurrent_input_mutations_are_not_lost(tmp_path) -> None:
    workspace = create_workspace(root=tmp_path)
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(6)
    processes = [
        context.Process(
            target=_record_input_worker,
            args=(str(tmp_path), workspace.workspace_id, barrier),
        )
        for _ in range(6)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    updated = load_workspace_state(root=tmp_path, workspace_id=workspace.workspace_id)
    assert len(updated.recent_inputs) == 6
