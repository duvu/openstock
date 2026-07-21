"""Tests for Section 10 — Safety and tool allowlist (tasks 10.1–10.4)."""

from __future__ import annotations

from vnalpha.assistant.tool_policy import SAFE_TOOLS
from vnalpha.chat.safety import (
    is_tool_allowed_in_chat,
)


class TestIsToolAllowedInChat:
    def test_each_canonical_safe_tool_is_allowed(self):
        for tool_name in SAFE_TOOLS:
            assert is_tool_allowed_in_chat(tool_name) is True
