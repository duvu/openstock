from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

textual_available = True
try:
    import textual  # noqa: F401
except ImportError:
    textual_available = False

skip_if_no_textual = pytest.mark.skipif(
    not textual_available, reason="textual not installed"
)


def _empty_conn():
    import duckdb

    from vnalpha.warehouse.migrations import run_migrations

    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    return conn


@pytest.fixture
def mock_get_connection():
    with patch(
        "vnalpha.warehouse.connection.get_connection", return_value=_empty_conn()
    ):
        yield


def _workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "workspaces"
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(root))
    return root


def _renderable_text(renderable: object) -> str:
    from rich.console import Console

    console = Console(record=True, width=120)
    console.print(renderable)
    return console.export_text()


def test_responsive_layout_policy_matches_breakpoint_rules() -> None:
    from vnalpha.tui.responsive_layout import ResponsiveLayoutController

    controller = ResponsiveLayoutController()

    assert controller.should_show_todo(140, user_preference=None) is True
    assert controller.should_show_todo(120, user_preference=None) is True
    assert controller.should_show_todo(119, user_preference=None) is False
    assert controller.should_show_todo(80, user_preference=True) is False
    assert controller.should_show_todo(140, user_preference=False) is False
    assert controller.should_show_todo(140, user_preference=True) is True


def test_workspace_todo_source_maps_workspace_state_to_items() -> None:
    from vnalpha.tui.todo_source import WorkspaceTodoSource
    from vnalpha.workspace_context.models import WorkspaceState, WorkspaceTask

    state = WorkspaceState(
        workspace_id="ws-1",
        title="FPT workspace",
        status="active",
        mode="research",
        created_at="2026-07-10T00:00:00+00:00",
        updated_at="2026-07-10T00:05:00+00:00",
        open_tasks=[
            WorkspaceTask(
                task_id="task-1",
                text="Review FPT breakout",
                status="in_progress",
                priority="high",
                created_at="2026-07-10T00:00:00+00:00",
                updated_at="2026-07-10T00:01:00+00:00",
            )
        ],
        warnings=["Data freshness warning"],
    )
    source = WorkspaceTodoSource(loader=lambda: state)

    items = source.load_items()

    assert [item.id for item in items] == ["task-1", "warning:1"]
    assert items[0].status == "active"
    assert items[0].priority == "p1"
    assert items[1].status == "blocked"
    assert items[1].source == "system"


def test_workspace_todo_source_maps_completed_tasks_to_done_items() -> None:
    from vnalpha.tui.todo_source import WorkspaceTodoSource
    from vnalpha.workspace_context.models import WorkspaceState, WorkspaceTask

    state = WorkspaceState(
        workspace_id="ws-1",
        title="FPT workspace",
        status="active",
        mode="research",
        created_at="2026-07-10T00:00:00+00:00",
        updated_at="2026-07-10T00:05:00+00:00",
        open_tasks=[
            WorkspaceTask(
                task_id="task-complete",
                text="Review completed FPT setup",
                status="completed",
                priority="medium",
                created_at="2026-07-10T00:00:00+00:00",
                updated_at="2026-07-10T00:04:00+00:00",
            )
        ],
    )

    items = WorkspaceTodoSource(loader=lambda: state).load_items()

    assert [(item.id, item.status) for item in items] == [("task-complete", "done")]


def test_composite_todo_source_deduplicates_items() -> None:
    from vnalpha.tui.todo_source import CompositeTodoSource, TodoItem, TodoSource

    class StaticSource(TodoSource):
        def __init__(self, items: list[TodoItem]) -> None:
            self._items = items

        def load_items(self) -> list[TodoItem]:
            return list(self._items)

    item = TodoItem(
        id="task-1",
        title="Review FPT breakout",
        status="open",
        priority="p1",
        source="workspace",
    )
    composite = CompositeTodoSource(
        [
            StaticSource([item]),
            StaticSource([item, TodoItem(id="task-2", title="Compact workspace")]),
        ]
    )

    items = composite.load_items()

    assert [todo.id for todo in items] == ["task-1", "task-2"]


@pytest.mark.parametrize(
    ("width", "expected_visible"),
    [
        (140, True),
        (120, True),
        (119, False),
        (80, False),
    ],
)
@skip_if_no_textual
@pytest.mark.asyncio
async def test_todo_panel_visibility_matches_widths(
    width: int, expected_visible: bool, mock_get_connection, tmp_path, monkeypatch
) -> None:
    from textual.widgets import ContentSwitcher, Input, Static

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.chat_panel import ChatPanel
    from vnalpha.tui.widgets.composer_input import ComposerInput
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.tui.widgets.status_bar import StatusBar
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    _workspace_root(tmp_path, monkeypatch)
    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True, size=(width, 40)) as pilot:
        await pilot.pause()
        assert len(pilot.app.query(StatusBar)) == 1
        assert len(pilot.app.query(OutputStream)) == 1
        assert len(pilot.app.query(ComposerInput)) == 1
        assert len(pilot.app.query(Input)) == 1
        assert len(pilot.app.query("#footer-hint")) == 1
        assert isinstance(pilot.app.query_one("#footer-hint"), Static)
        assert pilot.app.focused is pilot.app.query_one(Input)
        assert len(pilot.app.query(ContentSwitcher)) == 0
        assert len(pilot.app.query(ChatPanel)) == 0
        panels = pilot.app.query(TodoPanel)
        assert len(panels) == 1
        assert panels.first().display is expected_visible
        assert len(panels.first().query(Input)) == 0


@skip_if_no_textual
@pytest.mark.asyncio
async def test_toggle_hides_and_restores_todo_panel_on_wide_terminal(
    mock_get_connection, tmp_path, monkeypatch
) -> None:
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    _workspace_root(tmp_path, monkeypatch)
    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True, size=(140, 40)) as pilot:
        await pilot.pause()
        panel = pilot.app.query_one(TodoPanel)
        assert panel.display is True

        pilot.app.action_toggle_todo_panel()
        await pilot.pause()
        assert panel.display is False

        pilot.app.action_toggle_todo_panel()
        await pilot.pause()
        assert panel.display is True


@skip_if_no_textual
@pytest.mark.asyncio
async def test_toggle_cannot_force_panel_visible_on_narrow_terminal(
    mock_get_connection, tmp_path, monkeypatch
) -> None:
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    _workspace_root(tmp_path, monkeypatch)
    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True, size=(80, 40)) as pilot:
        await pilot.pause()
        panel = pilot.app.query_one(TodoPanel)
        assert panel.display is False

        pilot.app.action_toggle_todo_panel()
        await pilot.pause()
        assert panel.display is False


@skip_if_no_textual
@pytest.mark.asyncio
async def test_todo_panel_renders_empty_and_populated_states() -> None:
    from textual.app import App, ComposeResult

    from vnalpha.tui.todo_source import TodoItem
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    class TodoPanelHarness(App[None]):
        def __init__(self, panel: TodoPanel) -> None:
            super().__init__()
            self._panel = panel

        def compose(self) -> ComposeResult:
            yield self._panel

    empty_panel = TodoPanel()
    empty_app = TodoPanelHarness(empty_panel)
    async with empty_app.run_test(headless=True) as pilot:
        await pilot.pause()
        assert "No TODOs yet" in _renderable_text(empty_panel.renderable)

    populated_panel = TodoPanel(
        items=[
            TodoItem(id="1", title="Review FPT", status="active", priority="p0"),
            TodoItem(id="2", title="Stale benchmark", status="blocked", priority="p1"),
            TodoItem(id="3", title="Compact workspace", status="open", priority="p2"),
            TodoItem(
                id="4", title="Completed FPT review", status="done", priority="p2"
            ),
        ]
    )
    populated_app = TodoPanelHarness(populated_panel)
    async with populated_app.run_test(headless=True) as pilot:
        await pilot.pause()
        text = _renderable_text(populated_panel.renderable)
        assert "ACTIVE" in text
        assert "BLOCKED" in text
        assert "NEXT" in text
        assert "RECENTLY DONE" in text
        assert "Review FPT" in text
        assert "Stale benchmark" in text
        assert "Compact workspace" in text
        assert "Completed FPT review" in text


@skip_if_no_textual
@pytest.mark.asyncio
async def test_todo_panel_refresh_reloads_its_source() -> None:
    from textual.app import App, ComposeResult

    from vnalpha.tui.todo_source import TodoItem, TodoSource
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    class MutableSource(TodoSource):
        def __init__(self) -> None:
            self.items = [TodoItem(id="1", title="Initial task", status="open")]

        def load_items(self) -> list[TodoItem]:
            return list(self.items)

    class TodoPanelHarness(App[None]):
        def __init__(self, panel: TodoPanel) -> None:
            super().__init__()
            self._panel = panel

        def compose(self) -> ComposeResult:
            yield self._panel

    source = MutableSource()
    panel = TodoPanel(source=source)
    app = TodoPanelHarness(panel)
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        source.items = [TodoItem(id="2", title="Completed task", status="done")]
        panel.refresh_items()
        await pilot.pause()

        text = _renderable_text(panel.renderable)
        assert "Initial task" not in text
        assert "RECENTLY DONE" in text
        assert "Completed task" in text


@skip_if_no_textual
@pytest.mark.asyncio
async def test_wide_mount_emits_todo_panel_visible_event(
    mock_get_connection, tmp_path, monkeypatch
) -> None:
    from vnalpha.tui.app import VnAlphaApp

    _workspace_root(tmp_path, monkeypatch)
    with patch("vnalpha.tui.app._emit_audit_event") as emit_audit_event:
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(140, 40)) as pilot:
            await pilot.pause()

    assert any(
        call.args == ("TUI_TODO_PANEL_VISIBLE", "width=140")
        for call in emit_audit_event.call_args_list
    )


@skip_if_no_textual
@pytest.mark.asyncio
async def test_narrow_mount_emits_todo_panel_hidden_event(
    mock_get_connection, tmp_path, monkeypatch
) -> None:
    from vnalpha.tui.app import VnAlphaApp

    _workspace_root(tmp_path, monkeypatch)
    with patch("vnalpha.tui.app._emit_audit_event") as emit_audit_event:
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(80, 40)) as pilot:
            await pilot.pause()

    assert any(
        call.args == ("TUI_TODO_PANEL_HIDDEN", "width=80")
        for call in emit_audit_event.call_args_list
    )


@skip_if_no_textual
@pytest.mark.asyncio
async def test_toggle_emits_todo_panel_toggled_event(
    mock_get_connection, tmp_path, monkeypatch
) -> None:
    from vnalpha.tui.app import VnAlphaApp

    _workspace_root(tmp_path, monkeypatch)
    with patch("vnalpha.tui.app._emit_audit_event") as emit_audit_event:
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(140, 40)) as pilot:
            await pilot.pause()
            pilot.app.action_toggle_todo_panel()
            await pilot.pause()

    assert any(
        call.args == ("TUI_TODO_PANEL_TOGGLED", "visible=False")
        for call in emit_audit_event.call_args_list
    )


def test_todo_panel_refresh_event_is_redacted_to_count_only() -> None:
    from vnalpha.tui.todo_source import TodoItem
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    with patch("vnalpha.observability.audit.log_audit") as log_audit:
        panel = TodoPanel(
            items=[
                TodoItem(
                    id="secret-task",
                    title="Do not leak this sensitive task text",
                    status="active",
                    priority="p1",
                )
            ]
        )
        panel.refresh_items()

    summaries = [call.args[1] for call in log_audit.call_args_list]
    assert summaries
    assert all(summary == "count=1" for summary in summaries)
    assert all("sensitive task text" not in summary for summary in summaries)
