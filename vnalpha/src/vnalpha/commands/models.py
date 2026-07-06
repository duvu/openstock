"""Command data models for Phase 5.8 Research Workspace Command Layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CommandFilter:
    """A parsed filter expression (KEY OP VALUE)."""

    key: str
    op: Literal["=", "!=", ">", ">=", "<", "<=", "contains", "not_contains"]
    value: str


@dataclass
class ParsedCommand:
    """Result of parsing a slash-command string."""

    command_name: str
    raw_text: str
    positional: list[str] = field(default_factory=list)
    filters: list[CommandFilter] = field(default_factory=list)
    options: dict[str, str | bool] = field(default_factory=dict)


@dataclass
class ResultColumn:
    """Column definition for a result table."""

    name: str
    title: str


@dataclass
class ResultTable:
    """Tabular data in a command result."""

    title: str
    columns: list[ResultColumn]
    rows: list[list[Any]]


@dataclass
class ResultPanel:
    """Named key/value or text panel in a command result."""

    title: str
    content: str | dict[str, Any]


@dataclass
class ResultArtifact:
    """A named data artifact in a command result."""

    name: str
    data: Any


@dataclass
class CommandError:
    """Error information attached to a command result."""

    error_type: str
    message: str
    details: dict[str, Any] | None = None


@dataclass
class CommandResult:
    """Result of executing a slash command."""

    status: Literal["SUCCESS", "FAILED", "VALIDATION_ERROR"]
    title: str
    summary: str | None = None
    tables: list[ResultTable] = field(default_factory=list)
    panels: list[ResultPanel] = field(default_factory=list)
    artifacts: list[ResultArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: CommandError | None = None
