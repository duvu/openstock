from __future__ import annotations

from unittest.mock import patch

import pytest
from rich.console import Console, Group

from vnalpha.commands.models import CommandStatus


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


@pytest.mark.parametrize(
    ("raw", "status", "refreshes_workspace"),
    [
        ("/todo add Refresh after routing", CommandStatus.SUCCESS, True),
        ("/todo done task-1", CommandStatus.SUCCESS, True),
        ("/todo block task-1", CommandStatus.SUCCESS, True),
        ("/todo clear-done", CommandStatus.SUCCESS, True),
        ("/todo list", CommandStatus.SUCCESS, False),
        ("/todo add Refresh after routing", CommandStatus.EMPTY_RESULT, False),
        ("/todo add Refresh after routing", CommandStatus.PARTIAL, False),
        ("/todo add Refresh after routing", CommandStatus.FAILED, False),
        (
            "/todo add Refresh after routing",
            CommandStatus.VALIDATION_ERROR,
            False,
        ),
        ("/context status", CommandStatus.SUCCESS, True),
    ],
)
def test_workspace_refresh_predicate_accepts_only_successful_mutations(
    raw: str, status: CommandStatus, refreshes_workspace: bool
) -> None:
    from vnalpha.tui.workspace_context import refreshed_workspace_for_context_command

    with patch(
        "vnalpha.tui.workspace_context.load_active_workspace",
        return_value=_workspace_state(),
    ) as load_workspace:
        workspace = refreshed_workspace_for_context_command(raw, status)

    assert (workspace is not None) is refreshes_workspace
    assert load_workspace.called is refreshes_workspace


@pytest.mark.asyncio
async def test_todo_add_refreshes_panel_after_composer_worker_completes(
    mock_get_connection, tmp_path, monkeypatch
) -> None:
    from textual.widgets import Input

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.todo_panel import TodoPanel
    from vnalpha.workspace_context.lifecycle import get_or_create_latest_workspace

    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    task_text = "Refresh panel after routing"
    app = VnAlphaApp(date="2024-01-10")

    async with app.run_test(headless=True, size=(140, 40)) as pilot:
        await pilot.pause()
        assert app._router is not None
        executor = app._router._command_executor
        assert executor is not None
        composer = pilot.app.query_one("#composer-input-field", Input)
        panel = pilot.app.query_one("#todo-panel", TodoPanel)
        assert pilot.app.focused is composer
        assert task_text not in _renderable_text(panel.renderable)

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

        with patch.object(
            app, "_refresh_todo_panel", wraps=app._refresh_todo_panel
        ) as refresh_panel:
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
        refresh_panel.assert_called_once()
        assert task_text in _renderable_text(panel.renderable)
        assert pilot.app.focused is composer


def test_todo_panel_empty_hint_uses_todo_add_command() -> None:
    from vnalpha.tui.widgets.todo_panel import _render_items

    assert '/todo add "..."' in _renderable_text(_render_items([]))
