from __future__ import annotations

from unittest.mock import patch

import pytest
from rich.console import Console, Group


def _connection():
    import duckdb

    return duckdb.connect(":memory:")


@pytest.fixture
def mock_get_connection():
    with patch("vnalpha.warehouse.connection.get_connection", side_effect=_connection):
        yield


def _workspace_state():
    from vnalpha.workspace_context.models import WorkspaceState

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
    mock_get_connection, tmp_path, monkeypatch
) -> None:
    from textual.widgets import Input

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.todo_panel import TodoPanel
    from vnalpha.workspace_context.lifecycle import get_or_create_latest_workspace

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
        original_execute = executor.execute
        original_run_worker = app.run_worker

        def capture_result(*args, **kwargs):
            result = original_execute(*args, **kwargs)
            results.append(result)
            return result

        def capture_worker(*args, **kwargs):
            worker = original_run_worker(*args, **kwargs)
            workers.append(worker)
            return worker

        with patch.object(executor, "execute", side_effect=capture_result):
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
