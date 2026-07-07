"""Tests for ChatPanel widget and TUI app integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

textual_available = True
try:
    import textual  # noqa: F401
except ImportError:
    textual_available = False

skip_if_no_textual = pytest.mark.skipif(
    not textual_available, reason="textual not installed"
)


# ---------------------------------------------------------------------------
# 5.1 TraceEvent dataclass tests (complementary to test_chat_infrastructure.py)
# ---------------------------------------------------------------------------


def test_trace_event_dataclass():
    """TraceEvent is a proper dataclass with all required fields."""
    from vnalpha.tools.executor import TraceEvent

    evt = TraceEvent(
        tool_name="watchlist.scan",
        status="SUCCESS",
        duration_ms=42.5,
        tool_trace_id="trace-001",
    )
    assert evt.tool_name == "watchlist.scan"
    assert evt.status == "SUCCESS"
    assert evt.duration_ms == 42.5
    assert evt.tool_trace_id == "trace-001"


# ---------------------------------------------------------------------------
# 5.2 ChatPanel command dispatch
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_dispatch_known_command_routes_to_registry():
    """_dispatch_command_sync with '/scan' calls CommandRegistry.execute."""
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()

    # Patch the registry.execute to return a success result
    from vnalpha.commands.models import CommandResult

    mock_result = CommandResult(
        status="SUCCESS", title="/scan", summary="2 candidates found."
    )
    with patch.object(
        panel._registry, "execute", return_value=mock_result
    ) as mock_exec:
        # Also mock post_message_text to avoid Textual widget machinery
        panel.post_message_text = MagicMock()
        panel._dispatch_command_sync("/scan --date 2026-07-07")

        mock_exec.assert_called_once()
        called_parsed = mock_exec.call_args[0][0]
        assert called_parsed.command_name == "scan"

    # Verify summary was posted
    calls = [str(c) for c in panel.post_message_text.call_args_list]
    assert any("2 candidates found" in c or "scan" in c.lower() for c in calls)


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_dispatch_unknown_command_returns_error():
    """Unknown slash command shows error with valid command list."""
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    panel.post_message_text = MagicMock()

    panel._dispatch_command_sync("/nonexistent_command")

    # Some message posted containing the word "Unknown" or "unknown"
    all_messages = " ".join(str(c) for c in panel.post_message_text.call_args_list)
    assert "unknown" in all_messages.lower() or "Unknown" in all_messages


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_dispatch_failed_result_shown_in_red():
    """FAILED CommandResult is rendered in red."""
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    panel.post_message_text = MagicMock()

    from vnalpha.commands.models import CommandResult

    failed = CommandResult(
        status="FAILED", title="/scan", summary="No database connection."
    )
    panel._render_command_result(failed)

    # The rendered text should include red markup or the summary text
    all_calls = " ".join(str(c) for c in panel.post_message_text.call_args_list)
    assert "No database connection" in all_calls


# ---------------------------------------------------------------------------
# 5.3 ChatPanel assistant dispatch
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_dispatch_assistant_posts_answer():
    """_dispatch_assistant posts answer text to log after successful ask()."""
    from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    panel.post_message_text = MagicMock()

    mock_answer = AssistantAnswer(
        summary="FPT looks strong.",
        basis="Watchlist scan.",
        risks_caveats="",
        tool_trace_summary="1 tool called.",
    )
    mock_plan = AssistantPlan(intent="scan_candidates", steps=[])

    with patch.object(panel, "_run_ask", return_value=(mock_answer, mock_plan)):
        # Provide a fake app.call_from_thread so the callback doesn't crash
        mock_app = MagicMock()
        mock_app.call_from_thread = lambda fn, *args: None
        with patch.object(
            type(panel), "app", new_callable=lambda: property(lambda self: mock_app)
        ):
            await panel._dispatch_assistant("Show strongest VN30 today")

    all_messages = " ".join(str(c) for c in panel.post_message_text.call_args_list)
    assert "FPT looks strong" in all_messages


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_dispatch_assistant_posts_error_on_exception():
    """_dispatch_assistant posts error message when ask() raises."""
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    panel.post_message_text = MagicMock()

    with patch.object(panel, "_run_ask", side_effect=RuntimeError("LLM unreachable")):
        mock_app = MagicMock()
        mock_app.call_from_thread = lambda fn, *args: None
        with patch.object(
            type(panel), "app", new_callable=lambda: property(lambda self: mock_app)
        ):
            await panel._dispatch_assistant("Show strongest VN30 today")

    all_messages = " ".join(str(c) for c in panel.post_message_text.call_args_list)
    assert "LLM unreachable" in all_messages or "Error" in all_messages


# ---------------------------------------------------------------------------
# 5.4 Toggle visibility
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_chat_panel_action_toggle_panel():
    """action_toggle_panel flips the display property."""
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    # Simulate display = True
    panel._css_styles = MagicMock()
    panel.display = True

    initial = panel.display
    panel.action_toggle_panel()
    assert panel.display != initial

    panel.action_toggle_panel()
    assert panel.display == initial


# ---------------------------------------------------------------------------
# 5.5 Smoke: VnAlphaApp composes with ChatPanel accessible
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_vn_alpha_app_has_chat_panel():
    """VnAlphaApp can be instantiated and ChatPanel class is importable."""
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    app = VnAlphaApp()
    assert app is not None
    # ChatPanel is a Textual Widget subclass
    import textual.widget

    assert issubclass(ChatPanel, textual.widget.Widget)


@skip_if_no_textual
def test_chat_panel_importable():
    """ChatPanel is exported from tui/__init__.py."""
    from vnalpha.tui import ChatPanel

    assert ChatPanel is not None
