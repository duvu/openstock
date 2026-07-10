"""Data models for capability-governed research workspace commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, assert_never


class CommandStatus(str, Enum):
    SUCCESS = "SUCCESS"
    EMPTY_RESULT = "EMPTY_RESULT"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"


def status_color(status: CommandStatus) -> str:
    match status:
        case CommandStatus.SUCCESS:
            return "green"
        case CommandStatus.EMPTY_RESULT:
            return "cyan"
        case CommandStatus.PARTIAL:
            return "yellow"
        case CommandStatus.FAILED:
            return "red"
        case CommandStatus.VALIDATION_ERROR:
            return "yellow"
        case unreachable:
            assert_never(unreachable)


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

    status: CommandStatus
    title: str
    summary: str | None = None
    tables: list[ResultTable] = field(default_factory=list)
    panels: list[ResultPanel] = field(default_factory=list)
    artifacts: list[ResultArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: CommandError | None = None

    def __post_init__(self) -> None:
        self.status = CommandStatus(self.status)
