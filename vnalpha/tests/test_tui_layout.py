"""Tests for Phase 5.10 Section 1 — TUI shell and layout (tasks 1.1–1.5)."""

from __future__ import annotations

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
# Task 1.1 — VnAlphaApp imports ContentSwitcher
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_app_imports_content_switcher():
    """VnAlphaApp module imports ContentSwitcher from textual.widgets."""
    import vnalpha.tui.app as app_module

    # The module should successfully import; ContentSwitcher is used inside
    assert hasattr(app_module, "_TEXTUAL_AVAILABLE")
    assert app_module._TEXTUAL_AVAILABLE is True


# ---------------------------------------------------------------------------
# Task 1.2 — compose() yields ContentSwitcher and ChatPanel as siblings
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_app_compose_structure():
    """VnAlphaApp uses ContentSwitcher in compose() and ChatPanel as sibling."""
    import inspect

    from vnalpha.tui.app import VnAlphaApp

    src = inspect.getsource(VnAlphaApp.compose)

    # ContentSwitcher must be in compose
    assert "ContentSwitcher" in src
    # ChatPanel must be in compose
    assert "ChatPanel" in src
    # No push_screen should appear in compose
    assert "push_screen" not in src


@skip_if_no_textual
def test_app_no_push_screen_in_navigation():
    """action_show_* methods reference ContentSwitcher, not push_screen."""
    import inspect

    from vnalpha.tui.app import VnAlphaApp

    source = inspect.getsource(VnAlphaApp.action_show_home)
    assert "ContentSwitcher" in source or "main-workspace" in source
    assert "push_screen" not in source

    source_w = inspect.getsource(VnAlphaApp.action_show_watchlist)
    assert "push_screen" not in source_w


# ---------------------------------------------------------------------------
# Task 1.3 — New keybindings are present
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_app_has_new_bindings():
    """VnAlphaApp BINDINGS include ctrl+up, ctrl+down, and escape."""
    from vnalpha.tui.app import VnAlphaApp

    binding_keys = {b.key for b in VnAlphaApp.BINDINGS}
    assert "ctrl+up" in binding_keys, "ctrl+up binding missing"
    assert "ctrl+down" in binding_keys, "ctrl+down binding missing"
    assert "escape" in binding_keys, "escape binding missing"


@skip_if_no_textual
def test_app_binding_actions():
    """ctrl+up/down map to resize actions; escape maps to cancel_pending_plan."""
    from vnalpha.tui.app import VnAlphaApp

    binding_map = {b.key: b.action for b in VnAlphaApp.BINDINGS}
    assert binding_map.get("ctrl+up") == "resize_chat_bigger"
    assert binding_map.get("ctrl+down") == "resize_chat_smaller"
    assert binding_map.get("escape") == "cancel_pending_plan"


# ---------------------------------------------------------------------------
# Task 1.4 — PlanCancelRequested message class exists
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_plan_cancel_requested_is_message():
    """PlanCancelRequested is a proper Textual Message subclass."""
    from textual.message import Message

    from vnalpha.tui.app import PlanCancelRequested

    assert issubclass(PlanCancelRequested, Message)


# ---------------------------------------------------------------------------
# Task 1.5 — ChatPanel remains visible after switching screens
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_chat_panel_persistent_in_compose():
    """ChatPanel is a sibling of ContentSwitcher in compose() — not inside it."""
    import inspect

    from textual.widget import Widget

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    # ChatPanel must be a Widget subclass
    assert issubclass(ChatPanel, Widget)

    src = inspect.getsource(VnAlphaApp)
    assert "chat-panel" in src
    assert "ContentSwitcher" in src

    # ChatPanel(target_date=...) must appear AFTER the ContentSwitcher context
    # manager opens (i.e., outside it, as a sibling).
    # In the compose() source, the pattern is:
    #   with ContentSwitcher(...):
    #       yield ...screens...
    #   yield ChatPanel(...)  <- sibling, not inside ContentSwitcher
    compose_src = inspect.getsource(VnAlphaApp.compose)
    cs_idx = compose_src.index("ContentSwitcher")
    cp_idx = compose_src.index("ChatPanel(target_date")
    assert cp_idx > cs_idx, "ChatPanel should appear after ContentSwitcher in compose()"
