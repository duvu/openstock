"""TUI workspace tests — opencode-like chat-first layout (S9).

Covers all spec tasks 9.1-9.16. These tests replace the old ContentSwitcher /
ChatPanel / screen-switching tests in test_tui_pilot.py (which tested an
architecture that no longer exists in the default path).

Retired tests from test_tui_pilot.py:
  test_initial_screen_is_home           — ContentSwitcher removed
  test_switch_to_watchlist              — ContentSwitcher removed
  test_switch_to_commands               — ContentSwitcher removed
  test_switch_to_assistant              — ContentSwitcher removed
  test_switch_to_rejected               — ContentSwitcher removed
  test_switch_to_quality                — ContentSwitcher removed
  test_switch_to_outcomes               — ContentSwitcher removed
  test_chat_panel_remains_mounted_*     — ChatPanel removed from default
  test_chat_toggle_via_binding          — ChatPanel removed from default
  test_chat_controller_receives_*       — ChatPanel removed from default
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


# ---------------------------------------------------------------------------
# 9.1  app mounts without errors
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_1_app_mounts(mock_get_connection):
    """VnAlphaApp mounts without errors (9.1)."""
    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        assert pilot.app is not None


# ---------------------------------------------------------------------------
# 9.2  exactly one ComposerInput exists
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_2_exactly_one_composer_input(mock_get_connection):
    """Default DOM has exactly one ComposerInput (9.2)."""
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.composer_input import ComposerInput

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        composers = pilot.app.query(ComposerInput)
        assert len(composers) == 1


# ---------------------------------------------------------------------------
# 9.3  exactly one OutputStream exists
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_3_exactly_one_output_stream(mock_get_connection):
    """Default DOM has exactly one OutputStream (9.3)."""
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.output_stream import OutputStream

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        streams = pilot.app.query(OutputStream)
        assert len(streams) == 1


# ---------------------------------------------------------------------------
# 9.4  exactly one Textual Input widget in default DOM
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_4_exactly_one_input_widget(mock_get_connection):
    """Default DOM has exactly one Textual Input widget (9.4)."""
    from textual.widgets import Input

    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        inputs = pilot.app.query(Input)
        assert len(inputs) == 1


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_4b_narrow_terminal_hides_optional_panel(
    mock_get_connection, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True, size=(90, 30)) as pilot:
        assert pilot.app.query_one("#output-stream", OutputStream) is not None
        assert pilot.app.query_one("#todo-panel", TodoPanel).display is False


# ---------------------------------------------------------------------------
# 9.5  ContentSwitcher does NOT exist in default DOM
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_5_no_content_switcher(mock_get_connection):
    """ContentSwitcher is not present in the default DOM (9.5)."""
    from textual.widgets import ContentSwitcher

    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        switchers = pilot.app.query(ContentSwitcher)
        assert len(switchers) == 0


# ---------------------------------------------------------------------------
# 9.6  ChatPanel does NOT exist in default DOM
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_6_no_chat_panel(mock_get_connection):
    """ChatPanel is not present in the default DOM (9.6)."""
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        panels = pilot.app.query(ChatPanel)
        assert len(panels) == 0


# ---------------------------------------------------------------------------
# 9.7  CommandInput does NOT exist in default DOM
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_7_no_command_input_widget(mock_get_connection):
    """CommandInput widget is not present in the default DOM (9.7)."""
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.command_input import CommandInput

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        widgets = pilot.app.query(CommandInput)
        assert len(widgets) == 0


# ---------------------------------------------------------------------------
# 9.8  CommandResultPanel does NOT exist in default DOM
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_8_no_command_result_panel(mock_get_connection):
    """CommandResultPanel is not present in the default DOM (9.8)."""
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.command_result import CommandResultPanel

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        panels = pilot.app.query(CommandResultPanel)
        assert len(panels) == 0


# ---------------------------------------------------------------------------
# 9.9-9.10 OutputStream unit tests (no pilot needed)
# ---------------------------------------------------------------------------


def test_9_9_output_stream_methods_exist():
    """OutputStream exposes required public methods (9.9)."""
    from vnalpha.tui.widgets.output_stream import OutputStream

    for method in (
        "show_user_input",
        "show_assistant_message",
        "show_command_result",
        "show_error",
        "show_warning",
        "show_trace_event",
        "show_table_or_markup",
        "show_repair_bundle",
        "show_deploy_status",
        "clear_visible",
    ):
        assert hasattr(OutputStream, method), f"Missing method: {method}"


def test_9_10_composer_input_message_type():
    """ComposerInput.ComposerSubmitted carries text attribute (9.10)."""
    from vnalpha.tui.widgets.composer_input import ComposerInput

    msg = ComposerInput.ComposerSubmitted(text="hello")
    assert msg.text == "hello"


def test_9_10b_no_execution_controls_in_bindings() -> None:
    from vnalpha.tui.app import VnAlphaApp

    action_names = {binding.action for binding in VnAlphaApp.BINDINGS}
    forbidden_terms = {"trade", "order", "broker", "account", "portfolio"}

    assert {"open_artifact_detail", "artifact_back", "save_artifact_note"} <= action_names
    for action_name in action_names:
        for term in forbidden_terms:
            assert term not in action_name


# ---------------------------------------------------------------------------
# 9.11  Input routing unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_9_11_router_empty_is_noop():
    """Empty text does not call any handler (9.11)."""
    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch("vnalpha.tui.input_router.TuiInputRouter._setup_controller"):
        with patch("vnalpha.tui.input_router.TuiInputRouter._setup_executor"):
            from vnalpha.tui.input_router import TuiInputRouter

            router = TuiInputRouter(output_stream=output, target_date=None)
            router._chat_controller = MagicMock()
            router._command_executor = MagicMock()

    await router.route("   ")
    router._chat_controller.handle_turn.assert_not_called()
    router._command_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_9_12_router_slash_command_routes_to_executor():
    """Slash input routes to CommandExecutor.execute() (9.12)."""

    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch("vnalpha.tui.input_router.TuiInputRouter._setup_controller"):
        with patch("vnalpha.tui.input_router.TuiInputRouter._setup_executor"):
            from vnalpha.tui.input_router import TuiInputRouter

            router = TuiInputRouter(output_stream=output, target_date=None)

    mock_executor = MagicMock()
    mock_executor.execute.return_value = "result"
    router._command_executor = mock_executor
    router._chat_controller = MagicMock()

    with patch(
        "vnalpha.tui.routing.command_path.anyio.to_thread.run_sync",
        new_callable=AsyncMock,
    ) as mock_thread:
        mock_thread.return_value = "result"
        await router.route("/watchlist")

    mock_thread.assert_called_once()
    # first positional arg should be executor.execute
    call_args = mock_thread.call_args[0]
    assert call_args[0] == mock_executor.execute


@pytest.mark.asyncio
async def test_9_13_router_plain_text_routes_to_chat():
    """Plain text routes to ChatController.handle_turn() (9.13)."""

    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch("vnalpha.tui.input_router.TuiInputRouter._setup_controller"):
        with patch("vnalpha.tui.input_router.TuiInputRouter._setup_executor"):
            from vnalpha.tui.input_router import TuiInputRouter

            router = TuiInputRouter(output_stream=output, target_date=None)

    mock_controller = MagicMock()
    router._chat_controller = mock_controller
    router._command_executor = MagicMock()

    with patch(
        "vnalpha.tui.routing.chat_path.anyio.to_thread.run_sync",
        new_callable=AsyncMock,
    ) as mock_thread:
        mock_thread.return_value = None
        await router.route("what is the trend for FPT?")

    mock_thread.assert_called_once()
    call_args = mock_thread.call_args[0]
    assert call_args[0].func == mock_controller.handle_turn
    assert call_args[0].args == ("what is the trend for FPT?",)


@pytest.mark.asyncio
async def test_9_14_router_clear_calls_output_stream():
    """/clear routes to output_stream.clear_visible() (9.14)."""
    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch("vnalpha.tui.input_router.TuiInputRouter._setup_controller"):
        with patch("vnalpha.tui.input_router.TuiInputRouter._setup_executor"):
            from vnalpha.tui.input_router import TuiInputRouter

            router = TuiInputRouter(output_stream=output, target_date=None)

    await router.route("/clear")
    output.clear_visible.assert_called_once()


# ---------------------------------------------------------------------------
# 9.15  command output renders into OutputStream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_9_15_command_output_rendered_into_stream():
    """Command result is rendered into OutputStream via show_command_result (9.15)."""

    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch("vnalpha.tui.input_router.TuiInputRouter._setup_controller"):
        with patch("vnalpha.tui.input_router.TuiInputRouter._setup_executor"):
            from vnalpha.tui.input_router import TuiInputRouter

            router = TuiInputRouter(output_stream=output, target_date=None)

    router._command_executor = MagicMock()
    router._chat_controller = MagicMock()

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = "some result"
        with patch(
            "vnalpha.tui.input_router.TuiInputRouter._result_to_markup",
            return_value="[bold]result[/bold]",
        ):
            await router.route("/score")

    output.show_command_result.assert_called_once()


# ---------------------------------------------------------------------------
# 9.16  render errors captured by observability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_9_16_render_errors_captured_by_observability():
    """Exceptions from routing are captured by observability (9.16)."""

    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch("vnalpha.tui.input_router.TuiInputRouter._setup_controller"):
        with patch("vnalpha.tui.input_router.TuiInputRouter._setup_executor"):
            from vnalpha.tui.input_router import TuiInputRouter

            router = TuiInputRouter(output_stream=output, target_date=None)

    router._command_executor = MagicMock()
    router._chat_controller = MagicMock()

    exc = RuntimeError("boom")
    with patch(
        "vnalpha.tui.routing.command_path.anyio.to_thread.run_sync",
        new_callable=AsyncMock,
        side_effect=exc,
    ):
        with patch(
            "vnalpha.tui.routing.command_path.events.capture_render_error"
        ) as mock_capture:
            await router.route("/score")

    mock_capture.assert_called_once_with(exc)
    output.show_error.assert_called_once()
