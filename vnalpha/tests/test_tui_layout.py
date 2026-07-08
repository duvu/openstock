"""Tests for TUI layout — opencode-like chat-first workspace (updated for new architecture).

The new default VnAlphaApp composes OutputStream + ComposerInput.
ContentSwitcher and ChatPanel are no longer in the default path.

Retired (old architecture):
  test_app_imports_content_switcher      — ContentSwitcher removed from default
  test_app_compose_structure             — ContentSwitcher/ChatPanel removed
  test_app_no_push_screen_in_navigation — action_show_* removed
  test_app_has_new_bindings             — ctrl+up/down and ChatPanel bindings removed
  test_app_binding_actions              — resize_chat_bigger/smaller removed
  test_plan_cancel_requested_is_message — PlanCancelRequested removed
  test_chat_panel_persistent_in_compose — ChatPanel removed from default path
"""

from __future__ import annotations

import inspect

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
def test_app_module_importable():
    """VnAlphaApp module imports successfully."""
    import vnalpha.tui.app as app_module

    assert hasattr(app_module, "_TEXTUAL_AVAILABLE")
    assert app_module._TEXTUAL_AVAILABLE is True


@skip_if_no_textual
def test_app_compose_yields_output_stream():
    """VnAlphaApp.compose() yields OutputStream (not ContentSwitcher)."""
    from vnalpha.tui.app import VnAlphaApp

    src = inspect.getsource(VnAlphaApp.compose)
    assert "OutputStream" in src
    assert "ContentSwitcher" not in src


@skip_if_no_textual
def test_app_compose_yields_composer_input():
    """VnAlphaApp.compose() yields ComposerInput (not ChatPanel)."""
    from vnalpha.tui.app import VnAlphaApp

    src = inspect.getsource(VnAlphaApp.compose)
    assert "ComposerInput" in src
    assert "ChatPanel" not in src


@skip_if_no_textual
def test_app_has_escape_binding():
    """VnAlphaApp BINDINGS include escape for cancel_pending_plan."""
    from vnalpha.tui.app import VnAlphaApp

    binding_map = {b.key: b.action for b in VnAlphaApp.BINDINGS}
    assert "escape" in binding_map
    assert binding_map["escape"] == "cancel_pending_plan"


@skip_if_no_textual
def test_app_has_quit_binding():
    """VnAlphaApp BINDINGS include q for quit."""
    from vnalpha.tui.app import VnAlphaApp

    binding_keys = {b.key for b in VnAlphaApp.BINDINGS}
    assert "q" in binding_keys


@skip_if_no_textual
def test_app_has_action_cancel_pending_plan():
    """VnAlphaApp has action_cancel_pending_plan method."""
    from vnalpha.tui.app import VnAlphaApp

    assert hasattr(VnAlphaApp, "action_cancel_pending_plan")


@skip_if_no_textual
def test_app_has_action_approve_plan():
    """VnAlphaApp has action_approve_plan method."""
    from vnalpha.tui.app import VnAlphaApp

    assert hasattr(VnAlphaApp, "action_approve_plan")


@skip_if_no_textual
def test_app_has_action_clear_stream():
    """VnAlphaApp has action_clear_stream method."""
    from vnalpha.tui.app import VnAlphaApp

    assert hasattr(VnAlphaApp, "action_clear_stream")


@skip_if_no_textual
def test_legacy_screens_remain_importable():
    """Legacy screens are still importable even though they're not mounted by default."""
    from vnalpha.tui.screens.assistant import AssistantScreen
    from vnalpha.tui.screens.command import CommandScreen
    from vnalpha.tui.screens.home import HomeScreen
    from vnalpha.tui.screens.log_viewer import LogScreen
    from vnalpha.tui.screens.outcomes import OutcomeScreen
    from vnalpha.tui.screens.quality import QualityScreen
    from vnalpha.tui.screens.rejected import RejectedScreen
    from vnalpha.tui.screens.watchlist import WatchlistScreen

    for cls in (
        HomeScreen,
        WatchlistScreen,
        CommandScreen,
        AssistantScreen,
        RejectedScreen,
        QualityScreen,
        OutcomeScreen,
        LogScreen,
    ):
        assert cls is not None
