"""TUI smoke tests for command input, result panel, and CommandScreen (Task 7.6).

These tests run without a real terminal (textual not installed in test env = skip).
"""

from __future__ import annotations

import pytest

try:
    import textual  # noqa: F401

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

skip_if_no_textual = pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")


@skip_if_no_textual
class TestCommandScreenSmoke:
    def test_command_screen_imports(self):
        from vnalpha.tui.screens.command import CommandScreen

        assert CommandScreen is not None

    def test_command_screen_instantiate(self):
        from vnalpha.tui.screens.command import CommandScreen

        screen = CommandScreen(target_date="2026-07-06")
        assert screen.target_date == "2026-07-06"

    def test_command_screen_preserves_implicit_target_provenance(self):
        from vnalpha.tui.screens.command import CommandScreen

        screen = CommandScreen(target_date="2026-07-19", target_date_is_implicit=True)
        assert screen.target_date_is_implicit is True


@skip_if_no_textual
class TestCommandWidgets:
    def test_command_input_widget_imports(self):
        from vnalpha.tui.widgets.command_input import CommandInput

        assert CommandInput is not None

    def test_command_result_panel_imports(self):
        from vnalpha.tui.widgets.command_result import CommandResultPanel

        assert CommandResultPanel is not None

    def test_app_commands_available_via_composer(self):
        """TUI app routes /command input via ComposerInput (new workspace design)."""
        import inspect

        from vnalpha.tui.app import VnAlphaApp

        src = inspect.getsource(VnAlphaApp.compose)
        assert "ComposerInput" in src

    def test_command_screen_still_importable(self):
        """CommandScreen remains importable (legacy, not mounted by default)."""
        from vnalpha.tui.screens.command import CommandScreen

        assert CommandScreen is not None


class TestCommandWidgetsStatic:
    """Tests that don't require textual to be installed."""

    def test_command_screen_in_tui_dir(self):
        from pathlib import Path

        screens_dir = (
            Path(__file__).parent.parent / "src" / "vnalpha" / "tui" / "screens"
        )
        assert (screens_dir / "command.py").exists()

    def test_command_input_widget_in_widgets_dir(self):
        from pathlib import Path

        widgets_dir = (
            Path(__file__).parent.parent / "src" / "vnalpha" / "tui" / "widgets"
        )
        assert (widgets_dir / "command_input.py").exists()
        assert (widgets_dir / "command_result.py").exists()

    def test_command_screen_language_boundary(self):
        """CommandScreen must not contain trading language."""
        from pathlib import Path

        source = (
            Path(__file__).parent.parent
            / "src"
            / "vnalpha"
            / "tui"
            / "screens"
            / "command.py"
        ).read_text()
        forbidden = ["buy", "sell", "order", "portfolio", "broker", "position", "trade"]
        for word in forbidden:
            assert word not in source.lower(), (
                f"Forbidden word '{word}' found in command.py"
            )

    def test_textual_renderer_returns_rich_renderable(self):
        from io import StringIO

        from rich.console import Console, Group

        from vnalpha.commands.models import CommandResult
        from vnalpha.commands.renderers.textual_renderer import result_to_markup

        result = CommandResult(status="SUCCESS", title="test", summary="ok")
        markup = result_to_markup(result)
        assert isinstance(markup, Group)

        output = StringIO()
        Console(file=output, highlight=False).print(markup)
        assert "test" in output.getvalue()

    def test_rich_renderer_runs(self):
        """Rich renderer must accept a CommandResult without crashing."""
        from io import StringIO

        from rich.console import Console

        from vnalpha.commands.models import CommandResult
        from vnalpha.commands.renderers.rich_renderer import render_result

        result = CommandResult(status="SUCCESS", title="test", summary="works")
        buf = StringIO()
        console = Console(file=buf, highlight=False)
        render_result(result, console=console)
        output = buf.getvalue()
        assert "test" in output
