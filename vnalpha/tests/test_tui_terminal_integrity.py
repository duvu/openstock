from __future__ import annotations

import io
from unittest.mock import patch

import pytest

pytest.importorskip("textual")

from tests.tui_assertions import assert_workspace_regions


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 20), (100, 24), (120, 30), (160, 50)])
async def test_workspace_regions_remain_disjoint_at_supported_viewports(size) -> None:
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.output_stream import OutputStream

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=size) as pilot:
            await pilot.pause()
            pilot.app.query_one("#output-stream", OutputStream).show_assistant_message(
                "long transcript " * 1_000
            )
            await pilot.pause()
            assert_workspace_regions(pilot.app)


@pytest.mark.asyncio
async def test_suggestions_and_long_todo_content_remain_inside_workspace() -> None:
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.todo_source import TodoItem
    from vnalpha.tui.widgets.composer_input import ComposerInput
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(120, 30)) as pilot:
            await pilot.pause()
            composer = pilot.app.query_one("#composer-input", ComposerInput)
            todo = pilot.app.query_one("#todo-panel", TodoPanel)
            todo.set_items(
                [
                    TodoItem(
                        id=str(index),
                        title=f"Long task {index}",
                        status="active",
                        priority="p1",
                    )
                    for index in range(50)
                ]
            )
            composer.set_text("/")
            await pilot.pause()

            assert composer._max_suggestions == 10
            assert_workspace_regions(pilot.app)


@pytest.mark.asyncio
async def test_log_screen_owns_visible_regions_and_isolates_composer_input() -> None:
    from textual.widgets import Input

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.screens.log_viewer import LogScreen

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(80, 20)) as pilot:
            await pilot.pause()
            input_widget = pilot.app.query_one("#composer-input-field", Input)
            input_widget.value = "preserved"
            pilot.app.push_screen(LogScreen())
            await pilot.pause()

            log_screen = pilot.app.screen
            toolbar = log_screen.query_one("#log-toolbar")
            display = log_screen.query_one("#log-display")
            assert toolbar.region.bottom <= display.region.y
            assert display.region.bottom <= log_screen.region.bottom

            await pilot.press("x")
            assert input_widget.value == "preserved"
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen is not log_screen


@pytest.mark.asyncio
async def test_mounted_tui_keeps_structured_events_out_of_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import vnalpha.core.logging as logging_module
    from vnalpha.core.logging import LogSurface, configure_logging, get_logger
    from vnalpha.tui.app import VnAlphaApp

    stderr = io.StringIO()
    monkeypatch.setattr("sys.stderr", stderr)
    log_path = tmp_path / "vnalpha.log"
    configure_logging(log_path=log_path, surface=LogSurface.TUI)

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(100, 24)) as pilot:
            await pilot.pause()
            get_logger("mounted-tui").info("mounted tui log event")

    assert logging_module._QUEUE_LISTENER is not None
    logging_module._QUEUE_LISTENER.stop()
    logging_module._QUEUE_LISTENER = None
    assert stderr.getvalue() == ""
    assert "mounted tui log event" in log_path.read_text(encoding="utf-8")
