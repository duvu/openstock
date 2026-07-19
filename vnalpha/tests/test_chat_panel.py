"""Tests for ChatPanel widget and TUI app integration.

Updated per task 5.1.8: tests assert delegation to ChatController,
not local dispatch paths.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

textual_available = True
try:
    import textual  # noqa: F401
except ImportError:
    textual_available = False

skip_if_no_textual = pytest.mark.skipif(
    not textual_available, reason="textual not installed"
)


def test_trace_event_dataclass():
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


@skip_if_no_textual
def test_chat_panel_has_controller():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    assert hasattr(panel, "_chat_controller")
    assert panel._chat_controller is not None


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_input_delegates_to_controller():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    mock_controller = MagicMock()
    mock_controller.handle_turn = MagicMock(return_value=None)
    panel._chat_controller = mock_controller
    panel.post_message_text = MagicMock()

    await panel._dispatch_via_controller("/scan --date 2026-07-07")

    mock_controller.handle_turn.assert_called_once_with("/scan --date 2026-07-07")


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_approve_delegates_to_controller():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    mock_controller = MagicMock()
    panel._chat_controller = mock_controller

    panel.action_approve_plan()

    mock_controller.approve_pending_plan.assert_called_once()


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_cancel_delegates_to_controller():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    mock_controller = MagicMock()
    panel._chat_controller = mock_controller

    panel.action_cancel_plan()

    mock_controller.cancel_pending_plan.assert_called_once()


@skip_if_no_textual
@pytest.mark.asyncio
async def test_chat_panel_dispatch_error_handled():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    mock_controller = MagicMock()
    private_fragment = "CHAT_PANEL_SECRET_73"
    mock_controller.handle_turn.side_effect = RuntimeError(
        f"LLM unreachable password={private_fragment}"
    )
    panel._chat_controller = mock_controller
    panel.post_message_text = MagicMock()

    await panel._dispatch_via_controller("Show strongest VN30 today")

    all_messages = " ".join(str(c) for c in panel.post_message_text.call_args_list)
    assert "Assistant request failed. Check logs and retry." in all_messages
    assert private_fragment not in all_messages


@skip_if_no_textual
def test_chat_panel_writes_dynamic_text_without_active_markup():
    from rich.text import Text

    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    log = MagicMock()
    panel.query_one = MagicMock(return_value=log)

    panel.post_message_text("[link=https://example.invalid]bad[/link]", style="red")

    rendered = log.write.call_args.args[0]
    assert isinstance(rendered, Text)
    assert rendered.plain == "[link=https://example.invalid]bad[/link]"
    assert all("link" not in str(span.style) for span in rendered.spans)


@skip_if_no_textual
def test_chat_panel_action_toggle_panel():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    panel._css_styles = MagicMock()
    panel.display = True

    initial = panel.display
    panel.action_toggle_panel()
    assert panel.display != initial

    panel.action_toggle_panel()
    assert panel.display == initial


@skip_if_no_textual
@pytest.mark.asyncio
async def test_vn_alpha_app_has_chat_panel():
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    app = VnAlphaApp()
    assert app is not None
    import textual.widget

    assert issubclass(ChatPanel, textual.widget.Widget)


@skip_if_no_textual
def test_chat_panel_importable():
    from vnalpha.tui import ChatPanel

    assert ChatPanel is not None


@skip_if_no_textual
def test_chat_panel_no_local_dispatch_methods():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    assert not hasattr(panel, "_dispatch_command_sync")
    assert not hasattr(panel, "_dispatch_assistant")
    assert not hasattr(panel, "_run_ask")
    assert not hasattr(panel, "_registry")
