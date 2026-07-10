from __future__ import annotations

import json

from vnalpha.workspace_context.models import WorkspaceState
from vnalpha.workspace_context.storage import (
    acquire_workspace_lock,
    append_workspace_event,
    ensure_workspace_layout,
    load_latest_workspace_id,
    load_workspace_index,
    load_workspace_state,
    release_workspace_lock,
    resolve_workspace_root,
    save_latest_workspace_id,
    save_workspace_state,
)


def _sample_state() -> WorkspaceState:
    return WorkspaceState(
        workspace_id="ws-20260709-001",
        title="Test workspace",
        status="active",
        mode="research",
        created_at="2026-07-09T01:02:03+00:00",
        updated_at="2026-07-09T01:02:03+00:00",
        active_date="2026-07-09",
        active_symbols=["FPT"],
        assumptions=["Fresh warehouse data remains authoritative."],
    )


def test_resolve_workspace_root_prefers_env_override(monkeypatch, tmp_path) -> None:
    override = tmp_path / "custom-root"
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(override))

    resolved = resolve_workspace_root()

    assert resolved == override


def test_ensure_layout_and_state_round_trip(tmp_path) -> None:
    root = tmp_path / "workspace-root"
    workspace = ensure_workspace_layout(root=root, workspace_id="ws-20260709-001")
    state = _sample_state()

    assert workspace.workspace_dir == root / "ws-20260709-001"
    assert workspace.workspace_json_path.exists() is False
    assert workspace.events_path.exists()
    assert workspace.artifacts_dir.is_dir()
    assert workspace.exports_dir.is_dir()
    assert (root / "archive").is_dir()

    save_workspace_state(root=root, state=state)
    loaded = load_workspace_state(root=root, workspace_id=state.workspace_id)

    assert loaded == state
    assert (
        json.loads(workspace.workspace_json_path.read_text(encoding="utf-8"))["title"]
        == "Test workspace"
    )


def test_latest_pointer_and_event_append(tmp_path) -> None:
    root = tmp_path / "workspace-root"
    ensure_workspace_layout(root=root, workspace_id="ws-20260709-001")

    save_latest_workspace_id(root=root, workspace_id="ws-20260709-001")
    append_workspace_event(
        root=root,
        workspace_id="ws-20260709-001",
        event={
            "event_id": "evt-1",
            "event_type": "WORKSPACE_CREATED",
            "workspace_id": "ws-20260709-001",
        },
    )

    assert load_latest_workspace_id(root=root) == "ws-20260709-001"
    events_path = root / "ws-20260709-001" / "events.jsonl"
    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event_type"] == "WORKSPACE_CREATED"


def test_workspace_index_updates_when_state_is_saved(tmp_path) -> None:
    root = tmp_path / "workspace-root"
    first = _sample_state()
    second = WorkspaceState.from_dict(
        {
            **first.to_dict(),
            "workspace_id": "ws-20260709-002",
            "title": "Second workspace",
        }
    )

    save_workspace_state(root=root, state=first)
    save_workspace_state(root=root, state=second)

    index_payload = load_workspace_index(root=root)

    assert index_payload["workspace_ids"] == ["ws-20260709-001", "ws-20260709-002"]
    assert index_payload["count"] == 2


def test_lock_file_acquire_and_release(tmp_path) -> None:
    root = tmp_path / "workspace-root"
    paths = ensure_workspace_layout(root=root, workspace_id="ws-20260709-001")

    lock_path = acquire_workspace_lock(root=root, workspace_id="ws-20260709-001")

    assert lock_path == paths.lock_path
    assert lock_path.exists()

    release_workspace_lock(root=root, workspace_id="ws-20260709-001")

    assert lock_path.exists() is False
