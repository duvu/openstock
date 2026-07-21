"""Tests for InputHistory — shell-like input history navigation."""

from __future__ import annotations

from vnalpha.tui.input_history import InputHistory


class TestPush:
    def test_push_stores_text(self):
        h = InputHistory()
        h.push("/explain FPT")
        assert h.items() == ["/explain FPT"]
