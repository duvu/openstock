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
@pytest.mark.parametrize("size", [(80, 20), (100, 24), (120, 30), (160, 50)])
async def test_inline_drawer_returns_height_and_keeps_one_tail_worker(size) -> None:
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer
    from vnalpha.tui.widgets.output_stream import OutputStream

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=size) as pilot:
            await pilot.pause()
            output = pilot.app.query_one(OutputStream)
            drawer = pilot.app.query_one(DebugLogDrawer)
            closed_height = output.region.height

            for _ in range(3):
                pilot.app.action_toggle_log_viewer()
                await pilot.pause()
                assert drawer.display is True
                assert output.region.height < closed_height
                assert_workspace_regions(pilot.app)
                pilot.app.action_toggle_log_viewer()
                await pilot.pause()
                assert drawer.display is False
                assert output.region.height == closed_height

            assert drawer.tail_worker_start_count == 1


@pytest.mark.asyncio
async def test_suggestions_and_inline_logs_remain_inside_workspace() -> None:
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.composer_input import ComposerInput
    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(120, 30)) as pilot:
            await pilot.pause()
            composer = pilot.app.query_one("#composer-input", ComposerInput)
            drawer = pilot.app.query_one("#debug-log-drawer", DebugLogDrawer)
            pilot.app.action_toggle_log_viewer()
            composer.set_text("/")
            await pilot.pause()

            assert composer._max_suggestions == 10
            assert drawer.display is True
            assert_workspace_regions(pilot.app)


@pytest.mark.asyncio
async def test_inline_log_drawer_preserves_composer_and_screen() -> None:
    from textual.widgets import Input

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

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
            screen = pilot.app.screen
            pilot.app.action_toggle_log_viewer()
            await pilot.pause()

            drawer = pilot.app.query_one("#debug-log-drawer", DebugLogDrawer)
            toolbar = drawer.query_one("#debug-log-toolbar")
            display = drawer.query_one("#debug-log-display")
            assert drawer.display is True
            assert toolbar.region.bottom <= display.region.y
            assert display.region.bottom <= drawer.region.bottom
            assert pilot.app.screen is screen
            assert input_widget.value == "preserved"
            assert pilot.app.focused is input_widget
            pilot.app.action_toggle_log_viewer()
            await pilot.pause()
            assert drawer.display is False
            assert pilot.app.screen is screen


@pytest.mark.asyncio
async def test_escape_closes_inline_log_drawer_before_plan_cancellation() -> None:
    from textual.widgets import Input

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(100, 24)) as pilot:
            drawer = pilot.app.query_one(DebugLogDrawer)
            composer = pilot.app.query_one("#composer-input-field", Input)
            pilot.app.action_toggle_log_viewer()
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            assert drawer.display is False
            assert pilot.app.focused is composer


@pytest.mark.asyncio
async def test_page_keys_scroll_open_drawer_instead_of_transcript() -> None:
    from textual.widgets import RichLog

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(100, 24)) as pilot:
            drawer = pilot.app.query_one(DebugLogDrawer)
            pilot.app.action_toggle_log_viewer()
            log = drawer.query_one("#debug-log-display", RichLog)
            for index in range(100):
                log.write(f"log line {index}")
            await pilot.pause()
            log.scroll_end(animate=False, immediate=True)
            await pilot.pause()
            bottom = log.scroll_y

            await pilot.press("pageup")
            await pilot.pause()

            assert log.scroll_y < bottom


@pytest.mark.asyncio
async def test_transcript_scroll_bindings_preserve_composer_focus() -> None:
    from textual.widgets import Input, RichLog

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.output_stream import OutputStream

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(100, 24)) as pilot:
            output = pilot.app.query_one(OutputStream)
            for index in range(100):
                output.show_assistant_message(f"transcript line {index}")
            output.end()
            await pilot.pause()
            log = pilot.app.query_one("#output-log", RichLog)
            composer = pilot.app.query_one("#composer-input-field", Input)
            bottom = log.scroll_y

            await pilot.press("pageup")
            await pilot.pause()
            assert log.scroll_y < bottom
            assert pilot.app.focused is composer

            await pilot.press("home")
            await pilot.pause()
            assert log.scroll_y == 0
            assert pilot.app.focused is composer

            await pilot.press("end")
            await pilot.pause()
            assert log.is_vertical_scroll_end
            assert pilot.app.focused is composer


@pytest.mark.asyncio
async def test_status_boundary_redacts_secret_and_markup() -> None:
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    from vnalpha.tui.runtime_status import RuntimeState, RuntimeStatus
    from vnalpha.tui.widgets.status_bar import StatusBar

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield StatusBar()

    async with ProbeApp().run_test(headless=True) as pilot:
        status = pilot.app.query_one(StatusBar)
        status.update_status(
            RuntimeStatus(
                state=RuntimeState.ERROR,
                label="[red]failed[/red]",
                detail="api_key=super-secret",
            )
        )
        await pilot.pause()

        rendered = str(pilot.app.query_one("#status-text", Static).render())
        assert "super-secret" not in rendered
        assert "[REDACTED]" in rendered
        assert "super-secret" not in status._status.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(100, 24), (120, 30), (160, 50)])
async def test_footer_keeps_complete_action_segments(size) -> None:
    from vnalpha.tui.app import VnAlphaApp

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=size) as pilot:
            await pilot.pause()
            footer = pilot.app._footer_hint_text()

            assert "Ctrl+Y" in footer
            assert "F12 logs" in footer
            assert "/help" in footer
            assert not footer.endswith("· ")


@pytest.mark.asyncio
async def test_assistant_result_expands_to_wide_transcript() -> None:
    from textual.widgets import RichLog

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.models.conversation import AssistantAnswerMessage
    from vnalpha.tui.result_presentation import assistant_result_presentation
    from vnalpha.tui.widgets.output_stream import OutputStream

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(120, 30)) as pilot:
            output = pilot.app.query_one(OutputStream)
            output.show_result(
                assistant_result_presentation(
                    AssistantAnswerMessage(
                        "FPT research",
                        summary="FPT research summary.",
                        risks_caveats=(
                            "Giá chưa điều chỉnh; đây là nghiên cứu, "
                            "không phải khuyến nghị giao dịch."
                        ),
                    )
                )
            )
            await pilot.pause()

            log = pilot.app.query_one("#output-log", RichLog)
            rendered = "\n".join(line.text for line in log.lines)

            assert log.virtual_size.width > 100
            assert "khuyến nghị giao dịch." in rendered


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
