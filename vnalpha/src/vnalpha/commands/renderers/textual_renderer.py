"""Textual renderer stub for TUI command result display."""

from __future__ import annotations

from vnalpha.commands.models import CommandResult


def result_to_markup(result: CommandResult) -> str:
    """Convert a CommandResult to Rich markup for TUI display."""
    lines = []

    status_color = {
        "SUCCESS": "green",
        "FAILED": "red",
        "VALIDATION_ERROR": "yellow",
    }.get(result.status, "white")

    lines.append(f"[{status_color}]{result.title}[/{status_color}]")

    if result.summary:
        lines.append(result.summary)

    for rt in result.tables:
        lines.append(f"\n[bold]{rt.title}[/bold]")
        headers = " | ".join(c.title for c in rt.columns)
        lines.append(f"[dim]{headers}[/dim]")
        for row in rt.rows:
            lines.append(" | ".join(str(c) if c is not None else "—" for c in row))

    for rp in result.panels:
        lines.append(f"\n[bold]{rp.title}[/bold]")
        if isinstance(rp.content, dict):
            for k, v in rp.content.items():
                if v is not None:
                    lines.append(f"  {k}: {v}")
        else:
            lines.append(str(rp.content))

    for w in result.warnings:
        lines.append(f"[yellow]⚠ {w}[/yellow]")

    if result.error:
        lines.append(
            f"[red]Error ({result.error.error_type}): {result.error.message}[/red]"
        )

    return "\n".join(lines)
