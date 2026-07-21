"""Tests for ComposerInput history integration and default layout constraints."""

from __future__ import annotations

from vnalpha.tui.input_history import InputHistory
from vnalpha.tui.widgets.composer_input import ComposerInput


class TestComposerInputHistory:
    """Test that ComposerInput owns and uses InputHistory."""

    def test_composer_creates_default_history(self):
        composer = ComposerInput()
        assert isinstance(composer.history, InputHistory)
