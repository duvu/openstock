"""Textual renderer for TUI command result display.

Returns a Rich ``Group`` so that tables render with proper column
alignment and wrap responsively inside any ``RichLog`` widget.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from vnalpha.commands.models import CommandResult, status_color


def result_to_markup(result: CommandResult) -> RenderableType:
    """Convert a CommandResult to a Rich renderable for TUI display.

    Uses ``rich.table.Table`` for tabular data so columns are sized and
    wrapped responsively by Rich rather than truncated as plain text.
    Returns a ``rich.console.Group`` containing the ordered renderables
    (title, summary, tables, panels, warnings, error).
    """
    parts: list[RenderableType] = []

    color = status_color(result.status)

    parts.append(Text.from_markup(f"[{color}]{result.title}[/{color}]"))

    if result.summary:
        parts.append(Text.from_markup(result.summary))

    metadata_panel = _workflow_metadata_panel(result)
    if metadata_panel is not None:
        parts.append(Text.from_markup("\n[bold]Workflow status[/bold]"))
        parts.append(metadata_panel)

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
            lines = "\n".join(_mapping_lines(rp.content))
            parts.append(Text(lines))
        else:
            parts.append(Text(_value_text(rp.content)))

    if result.artifacts:
        artifact_lines = "\n".join(f"  artifact_id: {artifact.name}" for artifact in result.artifacts)
        parts.append(Text.from_markup("\n[bold]Artifacts[/bold]"))
        parts.append(Text(artifact_lines))

    for w in result.warnings:
        parts.append(Text.from_markup(f"[yellow]⚠ {w}[/yellow]"))

    if result.error:
        parts.append(
            Text.from_markup(
                f"[red]Error ({result.error.error_type}): {result.error.message}[/red]"
            )
        )

    return Group(*parts)


def _workflow_metadata_panel(result: CommandResult) -> Text | None:
    metadata = result.metadata
    if not isinstance(metadata, Mapping):
        return None

    visible: dict[str, object] = {}
    for key in (
        "artifact_id",
        "subject",
        "as_of_date",
        "workflow_status",
        "missing_data",
        "artifact_refs",
    ):
        value = metadata.get(key)
        if value not in (None, "", [], ()):
            visible[key] = value
    if not visible:
        return None
    return Text("\n".join(_mapping_lines(visible)))


def _mapping_lines(content: Mapping[str, object]) -> list[str]:
    return [
        f"  {key}: {_value_text(value)}"
        for key, value in content.items()
        if value is not None
    ]


def _value_text(value: object) -> str:
    if isinstance(value, Mapping):
        return "; ".join(f"{key}={_value_text(item)}" for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, str):
        return ", ".join(_value_text(item) for item in value) or "—"
    return str(value)
