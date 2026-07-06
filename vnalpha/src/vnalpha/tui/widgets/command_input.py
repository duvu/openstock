"""CommandInputWidget — slash command input bar for Phase 5.8."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input, Label, Static


class CommandInput(Static):
    """Command input bar that accepts slash commands.

    Emits a CommandSubmitted message when the user presses Enter.
    Shows a '/' prefix label to signal command mode.
    """

    BINDINGS = [
        Binding("escape", "clear_input", "Clear"),
    ]

    class CommandSubmitted(Message):
        """Emitted when the user submits a slash command."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]>[/bold cyan]", id="cmd-prefix")
        yield Input(
            placeholder="Type a slash command, e.g. /help",
            id="cmd-input",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            self.post_message(self.CommandSubmitted(text))

    def action_clear_input(self) -> None:
        self.query_one("#cmd-input", Input).clear()

    def focus_input(self) -> None:
        self.query_one("#cmd-input", Input).focus()
