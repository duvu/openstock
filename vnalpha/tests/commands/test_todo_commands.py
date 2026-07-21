from __future__ import annotations

from vnalpha.commands.models import CommandStatus
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry


def test_todo_commands_list_add_update_and_clear_persist_rows(tmp_path) -> None:
    registry = build_default_registry()

    empty = registry.execute(parse("/todo list"), root=tmp_path)
    added = registry.execute(parse("/todo add Review FPT"), root=tmp_path)
    task_id = added.panels[0].content["item_id"]
    listed = registry.execute(parse("/todo list"), root=tmp_path)
    completed = registry.execute(parse(f"/todo done {task_id}"), root=tmp_path)
    blocked = registry.execute(parse(f"/todo block {task_id}"), root=tmp_path)
    cleared = registry.execute(parse("/todo clear-done"), root=tmp_path)

    assert empty.panels[0].content["items"] == []
    assert added.status is CommandStatus.SUCCESS
    assert listed.panels[0].content["items"] == [
        {
            "id": task_id,
            "status": "pending",
            "priority": "medium",
            "text": "Review FPT",
            "updated_at": listed.panels[0].content["items"][0]["updated_at"],
        }
    ]
    assert completed.panels[0].content["status"] == "completed"
    assert blocked.panels[0].content["status"] == "blocked"
    assert cleared.panels[0].content["affected_count"] == 0
