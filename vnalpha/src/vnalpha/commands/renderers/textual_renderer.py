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
from vnalpha.core.text_safety import is_sensitive_key, sanitize_text


def result_to_markup(result: CommandResult) -> RenderableType:
    """Convert a CommandResult to a Rich renderable for TUI display.

    Uses ``rich.table.Table`` for tabular data so columns are sized and
    wrapped responsively by Rich rather than truncated as plain text.
    Returns a ``rich.console.Group`` containing the ordered renderables
    (title, summary, tables, panels, warnings, error).
    """
    parts: list[RenderableType] = []

    color = status_color(result.status)

    parts.append(Text(sanitize_text(result.title), style=color))

    if result.summary:
        parts.append(Text(sanitize_text(result.summary)))

    metadata_panel = _workflow_metadata_panel(result)
    if metadata_panel is not None:
        parts.append(Text("\nWorkflow status", style="bold"))
        parts.append(metadata_panel)

    for rt in result.tables:
        parts.append(Text(f"\n{sanitize_text(rt.title)}", style="bold"))
        tbl = Table(
            box=None,
            show_header=True,
            header_style="dim",
            expand=True,
            padding=(0, 1),
        )
        for col in rt.columns:
            tbl.add_column(
                sanitize_text(col.title),
                no_wrap=False,
                overflow="fold",
            )
        for row in rt.rows:
            cells = []
            for index, value in enumerate(row):
                column = rt.columns[index] if index < len(rt.columns) else None
                sensitive = column is not None and (
                    is_sensitive_key(column.name) or is_sensitive_key(column.title)
                )
                text = (
                    "[REDACTED]"
                    if sensitive and value is not None
                    else _value_text(value)
                    if value is not None
                    else "—"
                )
                if index < len(rt.columns) and rt.columns[index].name == "usage":
                    text = text.replace("|", "| ")
                cells.append(text)
            tbl.add_row(*cells)
        parts.append(tbl)

    for rp in result.panels:
        parts.append(Text(f"\n{sanitize_text(rp.title)}", style="bold"))
        if isinstance(rp.content, dict):
            lines = "\n".join(_mapping_lines(rp.content))
            parts.append(Text(lines))
        else:
            parts.append(Text(_value_text(rp.content)))

    if result.artifacts:
        artifact_lines = "\n".join(
            f"  artifact_id: {sanitize_text(artifact.name)}"
            for artifact in result.artifacts
        )
        parts.append(Text("\nArtifacts", style="bold"))
        parts.append(Text(artifact_lines))

    for w in result.warnings:
        parts.append(Text(f"⚠ {sanitize_text(w)}", style="yellow"))

    if result.error:
        parts.append(
            Text(
                "Error "
                f"({sanitize_text(result.error.error_type)}): "
                f"{sanitize_text(result.error.message)}",
                style="red",
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
        f"  {sanitize_text(key)}: "
        f"{'[REDACTED]' if is_sensitive_key(key) else _value_text(value)}"
        for key, value in content.items()
        if value is not None
    ]


def _value_text(value: object) -> str:
    if isinstance(value, Mapping):
        return "; ".join(
            f"{sanitize_text(key)}="
            f"{'[REDACTED]' if is_sensitive_key(key) else _value_text(item)}"
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, str):
        return ", ".join(_value_text(item) for item in value) or "—"
    return sanitize_text(value)
