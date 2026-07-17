from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from vnalpha.commands.models import CommandResult, status_color
from vnalpha.commands.renderers.textual_renderer import result_to_markup
from vnalpha.core.text_safety import is_sensitive_key, redact_structure, sanitize_text
from vnalpha.tui.models.conversation import AssistantAnswerMessage


@dataclass(frozen=True, slots=True)
class ResultPresentation:
    title: str
    body: RenderableType
    plain_text: str
    kind: str
    copyable_as_latest: bool
    metadata: Mapping[str, object]


def command_result_presentation(
    command: str, result: CommandResult
) -> ResultPresentation:
    metadata = MappingProxyType(redact_structure(dict(result.metadata or {})))
    body = Panel(
        result_to_markup(result),
        title=Text(_plain(result.title), style="bold"),
        border_style=status_color(result.status),
        padding=(0, 1),
        expand=True,
    )
    return ResultPresentation(
        title=_plain(result.title),
        body=body,
        plain_text=_command_plain_text(command, result),
        kind="command",
        copyable_as_latest=result.status.value not in {"FAILED", "VALIDATION_ERROR"},
        metadata=metadata,
    )


def assistant_result_presentation(
    message: AssistantAnswerMessage,
) -> ResultPresentation:
    metadata = MappingProxyType(redact_structure(dict(message.research_metadata or {})))
    parts: list[RenderableType] = [
        Text(f"Summary: {_plain(message.summary or message.text)}", style="bold"),
        Text(f"Risks: {_plain(message.risks_caveats or 'No explicit caveats.')}"),
    ]
    source_count, missing_count = message.source_counts()
    parts.append(Text(f"Sources: {source_count}  Missing data: {missing_count}"))
    if message.basis:
        parts.append(Text(f"Basis: {_plain(message.basis)}"))
    if message.missing_data:
        parts.append(
            Text(
                "Missing data:\n"
                + "\n".join(f"  - {_plain(item)}" for item in message.missing_data)
            )
        )
    if message.grounded_source_refs:
        parts.append(
            Text(
                "Grounded source refs:\n"
                + "\n".join(
                    f"  - {_plain(item)}" for item in message.grounded_source_refs
                )
            )
        )
    title = "Assistant research answer"
    border_style = "yellow" if message.missing_data else "green"
    return ResultPresentation(
        title=title,
        body=Panel(
            Group(*parts),
            title=Text(title, style="bold"),
            border_style=border_style,
            padding=(0, 1),
            expand=True,
        ),
        plain_text=_assistant_plain_text(message),
        kind="assistant",
        copyable_as_latest=True,
        metadata=metadata,
    )


def operational_result_presentation(
    command: str,
    text: str,
) -> ResultPresentation:
    safe_command = _plain(command)
    safe_text = _plain(text)
    title = f"Operational result · {safe_command}"
    return ResultPresentation(
        title=title,
        body=Panel(
            Text(safe_text),
            title=Text(title, style="bold"),
            border_style="cyan",
            padding=(0, 1),
            expand=True,
        ),
        plain_text=f"{title}\n{safe_text}",
        kind="operational",
        copyable_as_latest=True,
        metadata=MappingProxyType({"command": safe_command}),
    )


def _command_plain_text(command: str, result: CommandResult) -> str:
    lines = [
        _plain(result.title),
        f"Status: {result.status.value}",
        f"Command: {_plain(command)}",
    ]
    metadata = result.metadata if isinstance(result.metadata, Mapping) else {}
    subject = metadata.get("subject") or metadata.get("symbol")
    as_of_date = metadata.get("as_of_date")
    if subject not in (None, ""):
        lines.append(f"Symbol: {_plain(subject)}")
    if as_of_date not in (None, ""):
        lines.append(f"As of: {_plain(as_of_date)}")
    if result.summary:
        lines.append(_plain(result.summary))
    for table in result.tables:
        lines.append(_plain(table.title))
        lines.append("\t".join(_plain(column.title) for column in table.columns))
        for row in table.rows:
            cells: list[str] = []
            for index, value in enumerate(row):
                column = table.columns[index] if index < len(table.columns) else None
                sensitive = column is not None and (
                    is_sensitive_key(column.name) or is_sensitive_key(column.title)
                )
                cells.append(
                    "[REDACTED]"
                    if sensitive and value is not None
                    else "—"
                    if value is None
                    else _plain(value)
                )
            lines.append("\t".join(cells))
    for panel in result.panels:
        lines.append(_plain(panel.title))
        if isinstance(panel.content, Mapping):
            lines.extend(
                f"{_plain(key)}: "
                f"{'[REDACTED]' if is_sensitive_key(key) else _plain_value(value)}"
                for key, value in panel.content.items()
                if value is not None
            )
        else:
            lines.append(_plain(panel.content))
    if result.artifacts:
        lines.append("Artifacts")
        lines.extend(_plain(artifact.name) for artifact in result.artifacts)
    lines.extend(f"Warning: {_plain(warning)}" for warning in result.warnings)
    if result.error is not None:
        lines.append(
            f"Error ({_plain(result.error.error_type)}): {_plain(result.error.message)}"
        )
    return "\n".join(line for line in lines if line)


def _assistant_plain_text(message: AssistantAnswerMessage) -> str:
    lines = ["Assistant research answer"]
    metadata = message.research_metadata or {}
    subject = metadata.get("subject") or metadata.get("symbol")
    as_of_date = metadata.get("as_of_date")
    if subject not in (None, ""):
        lines.append(f"Symbol: {_plain(subject)}")
    if as_of_date not in (None, ""):
        lines.append(f"As of: {_plain(as_of_date)}")
    lines.extend(
        [
            f"Summary: {_plain(message.summary or message.text)}",
            f"Risks: {_plain(message.risks_caveats or 'No explicit caveats.')}",
        ]
    )
    source_count, missing_count = message.source_counts()
    lines.append(f"Sources: {source_count}  Missing data: {missing_count}")
    if message.basis:
        lines.append(f"Basis: {_plain(message.basis)}")
    if message.missing_data:
        lines.append("Missing data:")
        lines.extend(f"  - {_plain(item)}" for item in message.missing_data)
    if message.grounded_source_refs:
        lines.append("Grounded source refs:")
        lines.extend(f"  - {_plain(item)}" for item in message.grounded_source_refs)
    return "\n".join(lines)


def _plain_value(value: object) -> str:
    if isinstance(value, Mapping):
        return "; ".join(
            f"{_plain(key)}="
            f"{'[REDACTED]' if is_sensitive_key(key) else _plain_value(item)}"
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, str):
        return ", ".join(_plain_value(item) for item in value) or "—"
    return _plain(value)


def _plain(value: Any) -> str:
    return sanitize_text(value).strip()
