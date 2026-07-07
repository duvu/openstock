"""R4 ChatPanel wiring tests — delegation to ChatController.

Task coverage:
  5.1.1  ChatPanel creates a ChatController instance
  5.1.2  ChatPanel creates/resumes a chat_session for target date
  5.1.3  ChatPanel input submission calls ChatController.handle_turn(raw)
  5.1.4  ChatPanel approval action calls ChatController.approve_pending_plan()
  5.1.5  ChatPanel cancel action calls ChatController.cancel_pending_plan()
  5.1.6  No local command registry dispatch in ChatPanel
  5.1.7  No local assistant dispatch in ChatPanel
  5.1.8  ChatPanel tests assert delegation (this file)
  5.1.9  VnAlphaApp plan approval/cancel calls controller reliably
"""

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


@skip_if_no_textual
def test_chat_panel_creates_controller_on_init():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel(target_date="2024-01-10")
    assert panel._chat_controller is not None


@skip_if_no_textual
def test_chat_panel_passes_target_date_to_controller():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel(target_date="2024-01-10")
    ctrl = panel._chat_controller
    assert ctrl._target_date == "2024-01-10"


@skip_if_no_textual
@pytest.mark.asyncio
async def test_input_submission_calls_handle_turn():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel(target_date="2024-01-10")
    mock_ctrl = MagicMock()
    mock_ctrl.handle_turn = MagicMock(return_value=None)
    panel._chat_controller = mock_ctrl
    panel.post_message_text = MagicMock()

    await panel._dispatch_via_controller("show VNM analysis")

    mock_ctrl.handle_turn.assert_called_once_with("show VNM analysis")


@skip_if_no_textual
def test_action_approve_calls_approve_pending_plan():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    mock_ctrl = MagicMock()
    panel._chat_controller = mock_ctrl

    panel.action_approve_plan()

    mock_ctrl.approve_pending_plan.assert_called_once()


@skip_if_no_textual
def test_action_cancel_calls_cancel_pending_plan():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    mock_ctrl = MagicMock()
    panel._chat_controller = mock_ctrl

    panel.action_cancel_plan()

    mock_ctrl.cancel_pending_plan.assert_called_once()


@skip_if_no_textual
def test_no_local_command_registry_in_panel():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    assert not hasattr(panel, "_registry")
    assert not hasattr(panel, "_VALID_COMMANDS")
    assert not hasattr(panel, "_dispatch_command_sync")


@skip_if_no_textual
def test_no_local_assistant_dispatch_in_panel():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    assert not hasattr(panel, "_dispatch_assistant")
    assert not hasattr(panel, "_run_ask")


@skip_if_no_textual
@pytest.mark.asyncio
async def test_vn_alpha_app_approve_plan_calls_controller():
    from vnalpha.tui.app import VnAlphaApp

    with patch("vnalpha.warehouse.connection.get_connection"):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True) as pilot:
            panel = pilot.app.query_one("#chat-panel")
            from vnalpha.assistant.models import AssistantPlan

            mock_ctrl = MagicMock()
            mock_ctrl._pending_plan = AssistantPlan(intent="scan", steps=[])
            panel._chat_controller = mock_ctrl

            pilot.app.action_approve_plan()
            await pilot.pause()

            mock_ctrl.approve_pending_plan.assert_called_once()


@skip_if_no_textual
@pytest.mark.asyncio
async def test_vn_alpha_app_cancel_plan_calls_controller():
    from vnalpha.tui.app import VnAlphaApp

    with patch("vnalpha.warehouse.connection.get_connection"):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True) as pilot:
            panel = pilot.app.query_one("#chat-panel")
            mock_ctrl = MagicMock()
            panel._chat_controller = mock_ctrl

            pilot.app.action_cancel_pending_plan()
            await pilot.pause()

            mock_ctrl.cancel_pending_plan.assert_called_once()
