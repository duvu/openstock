"""CommandResultPanel — unified command history + result log for the TUI."""

from __future__ import annotations

from textual.widgets import RichLog


class CommandResultPanel(RichLog):
    """Scrollable log that shows command history and results in one place.

    Each submission appends:
      > /command
      <result or error markup>

    Older entries scroll up naturally — no separate history panel needed.
    """

    DEFAULT_CSS = """
    CommandResultPanel {
        border: round $panel;
        padding: 0 1;
        height: 1fr;
        min-height: 5;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=True, markup=True, wrap=True, **kwargs)

    def show_result(self, command: str, markup: str) -> None:
        """Append a command prompt line followed by its result."""
        self.write(f"[bold cyan]> {command}[/bold cyan]")
        self.write(markup)
        self.write("")  # blank separator

    def show_error(self, command: str, message: str) -> None:
        """Append a command prompt line followed by an error."""
        self.write(f"[bold cyan]> {command}[/bold cyan]")
        self.write(f"[red]Error: {message}[/red]")
        self.write("")  # blank separator
