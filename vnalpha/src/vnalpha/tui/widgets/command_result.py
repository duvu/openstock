"""CommandResultPanel — displays command results in the TUI."""

from __future__ import annotations

from textual.widgets import Static


class CommandResultPanel(Static):
    """Panel that displays the result of a slash command execution.

    Accepts Rich markup text for display.
    Shows a placeholder when no command has been run.
    """

    DEFAULT_CSS = """
    CommandResultPanel {
        border: round $panel;
        padding: 1;
        height: auto;
        min-height: 3;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            "[dim]Run a slash command (e.g. /help, /scan, /explain FPT)[/dim]",
            **kwargs,
        )

    def show_result(self, markup: str) -> None:
        """Update the panel with new command result markup."""
        self.update(markup)

    def show_error(self, message: str) -> None:
        """Update the panel with an error message."""
        self.update(f"[red]Error: {message}[/red]")
