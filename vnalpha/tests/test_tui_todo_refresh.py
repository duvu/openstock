from __future__ import annotations

from unittest.mock import patch

import duckdb
import pytest
from rich.console import Console, Group
from textual.widgets import Input

from vnalpha.commands.coordinated_executor import CoordinatedCommandExecutor
from vnalpha.core.config import reset_config
from vnalpha.tui.app import VnAlphaApp
from vnalpha.tui.widgets.todo_panel import TodoPanel
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.workspace_context.lifecycle import get_or_create_latest_workspace
from vnalpha.workspace_context.models import WorkspaceState


def _workspace_state():
    return WorkspaceState(
        workspace_id="ws-refresh",
        title="Refresh workspace",
        status="active",
        mode="research",
        created_at="2026-07-10T00:00:00+00:00",
        updated_at="2026-07-10T00:00:00+00:00",
    )


def _renderable_text(renderable: Group) -> str:
    console = Console(record=True, width=120)
    console.print(renderable)
    return console.export_text()


@pytest.mark.asyncio
async def test_todo_add_updates_workspace_without_side_panel(
    tmp_path, monkeypatch
) -> None:
    warehouse_path = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("VNALPHA_WAREHOUSE_PATH", str(warehouse_path))
    reset_config()
    connection = duckdb.connect(str(warehouse_path))
    try:
        run_migrations(conn=connection, emit_observability=False)
    finally:
        connection.close()
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    task_text = "Persist TODO after routing"
    app = VnAlphaApp(date="2024-01-10")

    async with app.run_test(headless=True, size=(140, 40)) as pilot:
        await pilot.pause()
        assert app._router is not None
        executor = app._router._command_executor
        assert executor is not None
        composer = pilot.app.query_one("#composer-input-field", Input)
        assert len(pilot.app.query(TodoPanel)) == 0
        assert pilot.app.focused is composer

        composer.value = f'/todo add "{task_text}"'
        results = []
        workers = []
        original_execute = CoordinatedCommandExecutor.execute
        original_run_worker = app.run_worker

        def capture_result(executor_instance, *args, **kwargs):
            result = original_execute(executor_instance, *args, **kwargs)
            results.append(result)
            return result

        def capture_worker(*args, **kwargs):
            worker = original_run_worker(*args, **kwargs)
            workers.append(worker)
            return worker

        with patch.object(CoordinatedCommandExecutor, "execute", new=capture_result):
            with patch.object(app, "run_worker", side_effect=capture_worker):
                await pilot.press("enter")
                await pilot.pause()
                await workers[0].wait()
        await pilot.pause()

        assert workers[0].error is None
        assert results[0].status == "SUCCESS"
        assert task_text in [
            task.text for task in get_or_create_latest_workspace().open_tasks
        ]
        assert pilot.app.focused is composer
