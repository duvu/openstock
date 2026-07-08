"""Textual renderer for TUI command result display.

Returns a Rich ``Group`` so that tables render with proper column
alignment and wrap responsively inside any ``RichLog`` widget.
"""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from vnalpha.commands.models import CommandResult


def result_to_markup(result: CommandResult) -> RenderableType:
    """Convert a CommandResult to a Rich renderable for TUI display.

    Uses ``rich.table.Table`` for tabular data so columns are sized and
    wrapped responsively by Rich rather than truncated as plain text.
    Returns a ``rich.console.Group`` containing the ordered renderables
    (title, summary, tables, panels, warnings, error).
    """
    parts: list[RenderableType] = []

    status_color = {
        "SUCCESS": "green",
        "FAILED": "red",
        "VALIDATION_ERROR": "yellow",
    }.get(result.status, "white")

    parts.append(Text.from_markup(f"[{status_color}]{result.title}[/{status_color}]"))

    if result.summary:
        parts.append(Text.from_markup(result.summary))

    for rt in result.tables:
        parts.append(Text.from_markup(f"\n[bold]{rt.title}[/bold]"))
        tbl = Table(
            box=None,
            show_header=True,
            header_style="dim",
            expand=True,
            padding=(0, 1),
        )
        for col in rt.columns:
            tbl.add_column(col.title, no_wrap=False)
        for row in rt.rows:
            tbl.add_row(*(str(c) if c is not None else "—" for c in row))
        parts.append(tbl)

    for rp in result.panels:
        parts.append(Text.from_markup(f"\n[bold]{rp.title}[/bold]"))
        if isinstance(rp.content, dict):
            lines = "\n".join(
                f"  {k}: {v}" for k, v in rp.content.items() if v is not None
            )
            parts.append(Text(lines))
        else:
            parts.append(Text(str(rp.content)))

    for w in result.warnings:
        parts.append(Text.from_markup(f"[yellow]⚠ {w}[/yellow]"))

    if result.error:
        parts.append(
            Text.from_markup(
                f"[red]Error ({result.error.error_type}): {result.error.message}[/red]"
            )
        )

    return Group(*parts)
