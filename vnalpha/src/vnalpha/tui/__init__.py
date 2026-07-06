"""vnalpha TUI package."""

from __future__ import annotations

try:
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    __all__ = ["ChatPanel"]
except ImportError:
    __all__ = []
