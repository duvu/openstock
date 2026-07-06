"""Rich CLI renderer for command results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vnalpha.commands.models import CommandResult


def render_result(result: CommandResult, console: Console | None = None) -> None:
    """Render a CommandResult to the terminal using Rich."""
    if console is None:
        console = Console()

    # Title
    status_color = {
        "SUCCESS": "green",
        "FAILED": "red",
        "VALIDATION_ERROR": "yellow",
    }.get(result.status, "white")

    console.print(f"[{status_color}]{result.title}[/{status_color}]")

    if result.summary:
        console.print(result.summary)

    # Tables
    for rt in result.tables:
        table = Table(title=rt.title, show_header=True, header_style="bold cyan")
        for col in rt.columns:
            table.add_column(col.title)
        for row in rt.rows:
            table.add_row(*[str(c) if c is not None else "—" for c in row])
        console.print(table)

    # Panels
    for rp in result.panels:
        if isinstance(rp.content, dict):
            lines = [f"  {k}: {v}" for k, v in rp.content.items() if v is not None]
            content_text = "\n".join(lines) if lines else "(empty)"
        else:
            content_text = str(rp.content)
        console.print(Panel(content_text, title=rp.title, border_style="dim"))

    # Warnings
    for w in result.warnings:
        console.print(f"[yellow]Warning: {w}[/yellow]")

    # Error
    if result.error:
        console.print(
            f"[red]Error ({result.error.error_type}): {result.error.message}[/red]"
        )
