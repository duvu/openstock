from __future__ import annotations

import duckdb
import pytest

from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.models import CommandStatus
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.workspace_context.lifecycle import get_or_create_latest_workspace


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


@pytest.mark.parametrize(
    "command",
    [
        "/todo",
        "/todo add",
        "/todo done",
        "/todo block",
        "/todo clear-done unexpected",
        "/todo unknown",
    ],
)
def test_todo_invalid_syntax_returns_validation_error_without_mutation(
    tmp_path, monkeypatch, command: str
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    executor = CommandExecutor(conn)

    result = executor.execute(command)

    assert result.status is CommandStatus.VALIDATION_ERROR
    assert get_or_create_latest_workspace(root=tmp_path).open_tasks == []
    conn.close()


def test_todo_unknown_id_returns_validation_error_without_mutation(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    executor = CommandExecutor(conn)

    result = executor.execute("/todo done missing-task")

    assert result.status is CommandStatus.VALIDATION_ERROR
    assert get_or_create_latest_workspace(root=tmp_path).open_tasks == []
    conn.close()


def test_help_documents_all_todo_command_forms() -> None:
    registry = build_default_registry()

    result = registry.execute(parse("/help"), registry=registry)

    todo_row = next(row for row in result.tables[0].rows if row[0] == "/todo")
    assert todo_row[2] == "/todo <list|add|done|block|clear-done> [text|id]"
