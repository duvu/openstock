"""Rich CLI renderer for command results."""

from __future__ import annotations

from rich.console import Console

from vnalpha.commands.models import CommandResult


def render_result(result: CommandResult, console: Console | None = None) -> None:
    """Render a CommandResult to the terminal using Rich."""
    if console is None:
        console = Console()
    from vnalpha.commands.renderers.textual_renderer import result_to_markup

    console.print(result_to_markup(result))
