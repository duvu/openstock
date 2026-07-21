from __future__ import annotations

import json

from vnalpha.workspace_context.lifecycle import create_workspace
from vnalpha.workspace_context.storage import load_workspace_state


def test_add_task_persists_immutable_task_and_redacts_item_event(
    tmp_path, monkeypatch
) -> None:
    from vnalpha.workspace_context import tasks

    audit_events: list[dict[str, str | int | bool]] = []
    monkeypatch.setattr(
        tasks,
        "emit_workspace_audit_event",
        lambda **event: audit_events.append(event),
    )
    workspace = create_workspace(root=tmp_path)

    updated = tasks.add_task(
        workspace,
        "Review confidential research notes",
        root=tmp_path,
    )

    assert workspace.open_tasks == []
    assert len(updated.open_tasks) == 1
    task = updated.open_tasks[0]
    assert task.status == "pending"
    assert task.priority == "medium"
    assert load_workspace_state(
        root=tmp_path, workspace_id=workspace.workspace_id
    ).open_tasks == [task]

    event_path = tmp_path / workspace.workspace_id / "events.jsonl"
    event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[-1])
    serialized_event = json.dumps(event)
    assert event["event_type"] == "TUI_TODO_ITEM_ADDED"
    assert event["metadata"] == {
        "item_id": task.task_id,
        "priority": "medium",
        "redaction_status": "redacted",
        "source": "composer_command",
        "status": "pending",
        "title_length": len(task.text),
    }
    assert task.text not in serialized_event
    assert audit_events == [
        {
            "event_type": "TUI_TODO_ITEM_ADDED",
            "workspace_id": workspace.workspace_id,
            "summary": "TODO item added",
            "metadata": event["metadata"],
        }
    ]
