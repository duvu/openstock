"""Command workspace screen — unified input + scrollable history/result log."""

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
    - A scrollable log that shows command history and results together
    """

    TITLE = "Command Workspace"

    def __init__(
        self, target_date: str, *, target_date_is_implicit: bool = False, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.target_date = target_date
        self.target_date_is_implicit = target_date_is_implicit

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            f"[bold]Phase 5.8 Research Command Workspace[/bold] | date: {self.target_date}",
            id="cmd-screen-title",
        )
        yield CommandResultPanel(id="cmd-result")
        yield CommandInput(id="cmd-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#cmd-bar", CommandInput).focus_input()

    def on_command_input_command_submitted(
        self, event: CommandInput.CommandSubmitted
    ) -> None:
        """Handle a submitted slash command."""
        text = event.text
        log = self.query_one("#cmd-result", CommandResultPanel)

        self.query_one("#cmd-bar", CommandInput).action_clear_input()

        try:
            from vnalpha.commands.executor import CommandExecutor
            from vnalpha.commands.renderers.textual_renderer import result_to_markup

            conn = None
            try:
                from vnalpha.warehouse.connection import get_connection
                from vnalpha.warehouse.migrations import run_migrations

                conn = get_connection()
                run_migrations(conn=conn)
            except Exception:
                pass

            result = CommandExecutor(
                conn,
                surface="tui",
                default_date=self.target_date,
                default_date_is_implicit=self.target_date_is_implicit,
            ).execute(text)
            markup = result_to_markup(result)
            log.show_result(text, markup)

        except Exception as exc:
            log.show_error(text, str(exc))
