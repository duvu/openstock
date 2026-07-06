"""Command workspace screen with input bar, result panel, and command history."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

from vnalpha.tui.widgets.command_input import CommandInput
from vnalpha.tui.widgets.command_result import CommandResultPanel


class CommandScreen(Screen):
    """Phase 5.8 command workspace screen.

    Contains:
    - A command input bar that accepts slash commands
    - A result panel that shows output
    - A history summary (recent commands in the current session)
    """

    TITLE = "Command Workspace"

    def __init__(self, target_date: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.target_date = target_date
        self._history: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            f"[bold]Phase 5.8 Research Command Workspace[/bold] | date: {self.target_date}",
            id="cmd-screen-title",
        )
        yield CommandInput(id="cmd-bar")
        yield CommandResultPanel(id="cmd-result")
        yield Footer()

    def on_command_input_command_submitted(
        self, event: CommandInput.CommandSubmitted
    ) -> None:
        """Handle a submitted slash command."""
        text = event.text
        self._history.append(text)
        result_panel = self.query_one("#cmd-result", CommandResultPanel)

        try:
            from vnalpha.commands.parser import parse as parse_command
            from vnalpha.commands.renderers.textual_renderer import result_to_markup
            from vnalpha.commands.setup import build_default_registry

            # Get warehouse connection (may not be available in TUI context without conn)
            conn = None
            try:
                from vnalpha.warehouse.connection import get_connection
                from vnalpha.warehouse.migrations import run_migrations
                conn = get_connection()
                run_migrations(conn=conn)
            except Exception:
                pass

            parsed = parse_command(text)
            registry = build_default_registry()
            result = registry.execute(parsed, conn=conn, registry=registry)
            markup = result_to_markup(result)
            result_panel.show_result(markup)

        except Exception as exc:
            result_panel.show_error(str(exc))
