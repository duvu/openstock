"""Tests for ComposerInput history integration and default layout constraints."""

from __future__ import annotations

from vnalpha.tui.input_history import InputHistory
from vnalpha.tui.widgets.composer_input import ComposerInput


class TestComposerInputHistory:
    """Test that ComposerInput owns and uses InputHistory."""

    def test_composer_creates_default_history(self):
        composer = ComposerInput()
        assert isinstance(composer.history, InputHistory)

    def test_composer_accepts_injected_history(self):
        h = InputHistory(max_items=10)
        composer = ComposerInput(history=h)
        assert composer.history is h

    def test_history_works_for_slash_commands(self):
        h = InputHistory()
        h.push("/explain FPT")
        h.push("/compare FPT MWG")
        assert h.previous("") == "/compare FPT MWG"
        assert h.previous("") == "/explain FPT"

    def test_history_works_for_natural_language(self):
        h = InputHistory()
        h.push("đánh giá FPT hôm nay")
        h.push("analyze market trend")
        assert h.previous("") == "analyze market trend"
        assert h.previous("") == "đánh giá FPT hôm nay"

    def test_history_works_for_chat_local_commands(self):
        h = InputHistory()
        h.push("/plan on")
        h.push("/new")
        assert h.previous("") == "/new"
        assert h.previous("") == "/plan on"


class TestDefaultLayoutConstraints:
    """Verify default TUI layout has no dashboard/switcher regression."""

    def test_app_imports_successfully(self):
        from vnalpha.tui.app import VnAlphaApp

        assert VnAlphaApp is not None

    def test_output_stream_imports(self):
        from vnalpha.tui.widgets.output_stream import OutputStream

        assert OutputStream is not None

    def test_composer_input_imports(self):
        from vnalpha.tui.widgets.composer_input import ComposerInput

        assert ComposerInput is not None

    def test_status_bar_imports(self):
        from vnalpha.tui.widgets.status_bar import StatusBar

        assert StatusBar is not None

    def test_no_content_switcher_in_app_module(self):
        """Ensure VnAlphaApp does not import or use ContentSwitcher."""
        import inspect

        from vnalpha.tui import app

        source = inspect.getsource(app)
        assert "ContentSwitcher" not in source

    def test_no_secondary_chat_panel_in_app(self):
        """Ensure VnAlphaApp does not mount a ChatPanel."""
        import inspect

        from vnalpha.tui import app

        source = inspect.getsource(app)
        assert "ChatPanel" not in source

    def test_no_command_screen_in_default_workflow(self):
        """Ensure no CommandScreen in the default compose path."""
        import inspect

        from vnalpha.tui import app

        source = inspect.getsource(app)
        assert "CommandScreen" not in source

    def test_status_bar_is_compact(self):
        """StatusBar has max-height 1 in its CSS."""
        from vnalpha.tui.widgets.status_bar import StatusBar

        css = getattr(StatusBar, "DEFAULT_CSS", "")
        assert "max-height: 1" in css
