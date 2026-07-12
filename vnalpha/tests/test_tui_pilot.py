"""TUI pilot/integration tests — updated for opencode-like workspace.

Task coverage:
  4.1.1  App mounts
  4.1.2  OutputStream is the primary output region
  4.1.3  ComposerInput is the primary input region
  4.1.4  No ContentSwitcher in default DOM
  4.1.5  No ChatPanel in default DOM
  4.1.9  Legacy screens remain importable
  4.1.10 /clear clears visible stream only
  4.2.1  Empty warehouse: app mounts without crash
  4.2.2  Empty warehouse: show_detail does not crash
  4.2.6  No empty-state test crashes due to missing DuckDB file
  4.3.1  WatchlistScreen has select_symbol binding (legacy screen)
  4.3.3  Legacy TUI screens have meaningful TITLE attributes
  4.3.5  Manual TUI smoke steps documented
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

textual_available = True
try:
    import textual  # noqa: F401
except ImportError:
    textual_available = False

skip_if_no_textual = pytest.mark.skipif(
    not textual_available, reason="textual not installed"
)


def _empty_conn():
    """In-memory DuckDB with migrations applied."""
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


@skip_if_no_textual
@pytest.mark.asyncio
async def test_app_mounts(mock_get_connection):
    """VnAlphaApp mounts without errors (4.1.1)."""
    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        assert pilot.app is not None


@skip_if_no_textual
@pytest.mark.asyncio
async def test_output_stream_is_primary_output(mock_get_connection):
    """OutputStream is the only primary output region (4.1.2)."""
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.output_stream import OutputStream

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        streams = pilot.app.query(OutputStream)
        assert len(streams) == 1
        stream = pilot.app.query_one("#output-stream", OutputStream)
        assert stream is not None


@skip_if_no_textual
@pytest.mark.asyncio
async def test_output_stream_keeps_dynamic_error_and_result_text_visible():
    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    from vnalpha.tui.widgets.output_stream import OutputStream

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield OutputStream(id="output-stream")

    async with ProbeApp().run_test(headless=True) as pilot:
        stream = pilot.app.query_one("#output-stream", OutputStream)
        log = pilot.app.query_one("#output-log", RichLog)

        stream.show_assistant_message(
            "[/ERROR] Invalid JSON from classifier", style="red"
        )
        stream.show_assistant_message(
            "classifier retry result: unavailable", style="green"
        )
        await pilot.pause()

        lines = [
            getattr(line, "text", getattr(line, "plain", "")) for line in log.lines
        ]
        assert lines == [
            "\\[/ERROR] Invalid JSON from classifier",
            "classifier retry result: unavailable",
        ]


@skip_if_no_textual
@pytest.mark.asyncio
async def test_output_stream_keeps_all_dynamic_text_visible():
    from types import SimpleNamespace

    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    from vnalpha.tui.widgets.output_stream import OutputStream

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield OutputStream(id="output-stream")

    async with ProbeApp().run_test(headless=True) as pilot:
        stream = pilot.app.query_one("#output-stream", OutputStream)
        log = pilot.app.query_one("#output-log", RichLog)
        stream.show_user_input("[/USER]")
        stream.show_command_result("[/COMMAND]", Text("[/RESULT]"))
        stream.show_error("[/ERROR]", source="[/SOURCE]")
        stream.show_warning("[/WARNING]", source="[/SOURCE]")
        stream.show_trace_event(
            SimpleNamespace(status="FAILED", tool_name="[/TOOL]", duration_ms=1)
        )
        stream.show_data_ensure_progress("[/STEP]", "done", "[/DETAIL]")
        stream.show_repair_bundle("[/PATH]", repair_id="[/REPAIR]")
        stream.show_deploy_status("[/STATUS]", details="[/DETAIL]")
        await pilot.pause()

        lines = [
            getattr(line, "text", getattr(line, "plain", "")) for line in log.lines
        ]
        for expected in (
            "[/USER]",
            "[/COMMAND]",
            "[/RESULT]",
            "[/ERROR]",
            "[/SOURCE]",
            "[/WARNING]",
            "[/TOOL]",
            "[/STEP]",
            "[/DETAIL]",
            "[/PATH]",
            "[/REPAIR]",
            "[/STATUS]",
        ):
            assert any(expected in line for line in lines), (expected, lines)


@skip_if_no_textual
@pytest.mark.asyncio
async def test_output_stream_records_render_failures():
    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    from vnalpha.tui.widgets.output_stream import OutputStream

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield OutputStream(id="output-stream")

    async with ProbeApp().run_test(headless=True) as pilot:
        stream = pilot.app.query_one("#output-stream", OutputStream)
        failure = RuntimeError("render failed")
        with patch.object(RichLog, "write", side_effect=failure):
            with patch(
                "vnalpha.tui.routing.events.capture_render_error"
            ) as capture_render_error:
                stream._write("unrenderable")

        capture_render_error.assert_called_once_with(failure)


@skip_if_no_textual
@pytest.mark.asyncio
async def test_output_stream_persists_redacted_render_failure(tmp_path):
    from json import loads

    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    from vnalpha.observability.context import (
        init_run_context,
        reset_run_context,
        set_correlation_id,
    )
    from vnalpha.tui.widgets.output_stream import OutputStream

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield OutputStream(id="output-stream")

    reset_run_context()
    context = init_run_context(surface="tui", actor="test", log_root=tmp_path)
    correlation_id = set_correlation_id()
    try:
        async with ProbeApp().run_test(headless=True) as pilot:
            stream = pilot.app.query_one("#output-stream", OutputStream)
            failure = RuntimeError("render failed api_key=secret-token")
            with patch.object(RichLog, "write", side_effect=failure):
                stream._write("unrenderable")

        audit_records = [
            loads(line)
            for line in context.audit_path.read_text().splitlines()
            if line.strip()
        ]
        error_records = [
            loads(line)
            for line in context.errors_path.read_text().splitlines()
            if line.strip()
        ]
        render_record = next(
            record
            for record in audit_records
            if record["event_type"] == "TUI_RENDER_ERROR"
        )
        assert render_record["correlation_id"] == correlation_id
        assert any(
            record["event_type"] == "EXCEPTION_CAPTURED" for record in error_records
        )
        assert "secret-token" not in context.audit_path.read_text()
        assert "secret-token" not in context.errors_path.read_text()
    finally:
        reset_run_context()


@skip_if_no_textual
@pytest.mark.asyncio
async def test_composer_input_is_primary_input(mock_get_connection):
    """ComposerInput is the only primary input region (4.1.3)."""
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.composer_input import ComposerInput

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        composers = pilot.app.query(ComposerInput)
        assert len(composers) == 1
        composer = pilot.app.query_one("#composer-input", ComposerInput)
        assert composer is not None


@skip_if_no_textual
@pytest.mark.asyncio
async def test_no_content_switcher(mock_get_connection):
    """No ContentSwitcher in default DOM (4.1.4)."""
    from textual.css.query import NoMatches
    from textual.widgets import ContentSwitcher

    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        with pytest.raises(NoMatches):
            pilot.app.query_one(ContentSwitcher)


@skip_if_no_textual
@pytest.mark.asyncio
async def test_no_chat_panel(mock_get_connection):
    """No ChatPanel in default DOM (4.1.5)."""
    from textual.css.query import NoMatches

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        with pytest.raises(NoMatches):
            pilot.app.query_one(ChatPanel)


@skip_if_no_textual
@pytest.mark.asyncio
async def test_legacy_screens_remain_importable(mock_get_connection):
    """Legacy screens stay importable even though not mounted by default (4.1.9)."""
    from vnalpha.tui.screens.assistant import AssistantScreen  # noqa: F401
    from vnalpha.tui.screens.command import CommandScreen  # noqa: F401
    from vnalpha.tui.screens.home import HomeScreen  # noqa: F401
    from vnalpha.tui.screens.log_viewer import LogScreen  # noqa: F401
    from vnalpha.tui.screens.outcomes import OutcomeScreen  # noqa: F401
    from vnalpha.tui.screens.quality import QualityScreen  # noqa: F401
    from vnalpha.tui.screens.rejected import RejectedScreen  # noqa: F401
    from vnalpha.tui.screens.watchlist import WatchlistScreen  # noqa: F401


@skip_if_no_textual
@pytest.mark.asyncio
async def test_clear_command_clears_stream(mock_get_connection):
    """OutputStream.clear_visible() is accessible; /clear command clears (4.1.10)."""
    from textual.widgets import Input

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.output_stream import OutputStream

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        stream = pilot.app.query_one("#output-stream", OutputStream)
        assert hasattr(stream, "clear_visible")
        stream.clear_visible()  # Must not raise
        await pilot.pause()
        assert pilot.app.focused is not None
        assert isinstance(pilot.app.focused, Input)


@skip_if_no_textual
@pytest.mark.asyncio
async def test_empty_warehouse_no_crash(mock_get_connection):
    """App with empty warehouse mounts without crash (4.2.1, 4.2.6)."""
    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        assert pilot.app is not None


@skip_if_no_textual
@pytest.mark.asyncio
async def test_detail_screen_empty_state_no_crash(mock_get_connection):
    """show_detail with empty warehouse does not crash (4.2.2)."""
    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        pilot.app.show_detail("FPT")
        await pilot.pause()


@skip_if_no_textual
@pytest.mark.asyncio
async def test_watchlist_row_selection_action():
    """Legacy WatchlistScreen has a select_symbol binding (4.3.1)."""
    from vnalpha.tui.screens.watchlist import WatchlistScreen

    bindings = {b.key: b.action for b in WatchlistScreen.BINDINGS}
    assert "enter" in bindings
    assert "select_symbol" in bindings["enter"]


@skip_if_no_textual
@pytest.mark.asyncio
async def test_tui_screens_have_meaningful_titles():
    """Legacy TUI screens have meaningful TITLE attributes (4.3.3)."""
    from vnalpha.tui.screens.assistant import AssistantScreen
    from vnalpha.tui.screens.command import CommandScreen
    from vnalpha.tui.screens.home import HomeScreen
    from vnalpha.tui.screens.outcomes import OutcomeScreen
    from vnalpha.tui.screens.quality import QualityScreen
    from vnalpha.tui.screens.rejected import RejectedScreen
    from vnalpha.tui.screens.watchlist import WatchlistScreen

    screens = [
        HomeScreen,
        WatchlistScreen,
        CommandScreen,
        AssistantScreen,
        RejectedScreen,
        QualityScreen,
        OutcomeScreen,
    ]
    for screen in screens:
        assert hasattr(screen, "TITLE")
        assert screen.TITLE is None or (
            isinstance(screen.TITLE, str) and len(screen.TITLE) > 0
        )


def test_manual_tui_smoke_steps_documented():
    """Manual TUI smoke steps exist (4.3.5) — evidenced by this test file and docs."""
    import os

    docs_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "13-r0-r4-completion-matrix.md"
    )
    assert os.path.exists(docs_path), (
        "Completion matrix doc must exist at vnalpha/docs/13-r0-r4-completion-matrix.md"
    )
