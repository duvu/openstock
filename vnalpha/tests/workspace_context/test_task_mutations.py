from __future__ import annotations

import json

import pytest

from vnalpha.commands.errors import CommandValidationError
from vnalpha.workspace_context.lifecycle import create_workspace
from vnalpha.workspace_context.models import WorkspaceState
from vnalpha.workspace_context.storage import load_workspace_state, save_workspace_state


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


def test_update_and_clear_done_tasks_preserve_noncompleted_items(tmp_path) -> None:
    from vnalpha.workspace_context import tasks

    workspace = create_workspace(root=tmp_path)
    pending = tasks.add_task(workspace, "Keep this task", root=tmp_path)
    completed = tasks.add_task(pending, "Finish this task", root=tmp_path)
    done_task_id = completed.open_tasks[1].task_id

    marked_done = tasks.update_task_status(
        completed, done_task_id, "completed", root=tmp_path
    )
    cleared_completed = tasks.clear_done_tasks(marked_done, root=tmp_path)
    blocked = tasks.update_task_status(
        cleared_completed,
        cleared_completed.open_tasks[0].task_id,
        "blocked",
        root=tmp_path,
    )
    legacy_done = WorkspaceState.from_dict(
        {
            **blocked.to_dict(),
            "open_tasks": [
                {
                    **blocked.open_tasks[0].to_dict(),
                    "status": "done",
                }
            ],
        }
    )
    save_workspace_state(root=tmp_path, state=legacy_done)
    cleared = tasks.clear_done_tasks(legacy_done, root=tmp_path)

    assert [(task.text, task.status) for task in marked_done.open_tasks] == [
        ("Keep this task", "pending"),
        ("Finish this task", "completed"),
    ]
    assert [(task.text, task.status) for task in blocked.open_tasks] == [
        ("Keep this task", "blocked")
    ]
    assert cleared.open_tasks == []


def test_unknown_task_id_does_not_persist_a_mutation(tmp_path) -> None:
    from vnalpha.workspace_context import tasks

    workspace = create_workspace(root=tmp_path)
    updated = tasks.add_task(workspace, "Stable task", root=tmp_path)

    with pytest.raises(CommandValidationError):
        tasks.update_task_status(updated, "missing-task", "completed", root=tmp_path)

    persisted = load_workspace_state(root=tmp_path, workspace_id=workspace.workspace_id)
    assert persisted.open_tasks == updated.open_tasks
