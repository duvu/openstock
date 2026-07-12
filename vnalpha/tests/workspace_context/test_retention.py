from __future__ import annotations

import json

from vnalpha.workspace_context.lifecycle import (
    create_workspace,
    record_input,
    record_warning,
)
from vnalpha.workspace_context.retention import enforce_retention
from vnalpha.workspace_context.storage import (
    ensure_workspace_layout,
    load_workspace_state,
)
from vnalpha.workspace_context.tasks import add_task


def test_input_retention_archives_entries_outside_configured_bound(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_MAX_INPUTS", "2")
    workspace = create_workspace(root=tmp_path)

    for index in range(3):
        record_input(workspace, f"input-{index}", "user", root=tmp_path)

    state = load_workspace_state(root=tmp_path, workspace_id=workspace.workspace_id)
    archive_path = tmp_path / workspace.workspace_id / "archive" / "inputs.jsonl"
    archived = [json.loads(line) for line in archive_path.read_text().splitlines()]

    assert [item.summary for item in state.recent_inputs] == ["input-1", "input-2"]
    assert len(archived) == 1
    assert archived[0]["summary"] == "input-0"


def test_event_retention_archives_old_events(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_MAX_EVENTS", "2")
    workspace = create_workspace(root=tmp_path)
    paths = ensure_workspace_layout(root=tmp_path, workspace_id=workspace.workspace_id)
    paths.events_path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    enforce_retention(
        root=tmp_path,
        state=load_workspace_state(root=tmp_path, workspace_id=workspace.workspace_id),
    )

    assert paths.events_path.read_text(encoding="utf-8").splitlines() == [
        "two",
        "three",
    ]
    assert (paths.workspace_dir / "archive" / "events.jsonl").read_text(
        encoding="utf-8"
    ).splitlines() == ['{"event": "one"}']


def test_warning_and_task_text_are_redacted_before_persistence(tmp_path) -> None:
    workspace = create_workspace(root=tmp_path)
    record_warning(workspace, "api_key=warning-secret", root=tmp_path)
    add_task(workspace, "password=task-secret review FPT", root=tmp_path)

    state = load_workspace_state(root=tmp_path, workspace_id=workspace.workspace_id)

    assert state.warnings == ["api_key=[REDACTED]"]
    assert state.open_tasks[0].text == "password=[REDACTED] review FPT"
