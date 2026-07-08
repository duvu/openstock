"""Tool data models for Phase 5.8 Local Tool Registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolPermission(str, Enum):
    """Phase 5.8 tool permission set.

    These are the ONLY permitted permissions. The following are explicitly
    excluded and must never be added:
        NETWORK_ACCESS, PYTHON_EXECUTION, MCP_TOOL_CALL,
        CODEBASE_MUTATION, BROKER_EXECUTION
    """

    READ_WATCHLIST = "READ_WATCHLIST"
    READ_FEATURES = "READ_FEATURES"
    READ_SCORE = "READ_SCORE"
    READ_QUALITY = "READ_QUALITY"
    READ_LINEAGE = "READ_LINEAGE"
    WRITE_NOTE = "WRITE_NOTE"
    READ_HISTORY = "READ_HISTORY"
    WRITE_DATA = "WRITE_DATA"


# Forbidden permissions — must never appear in any tool spec
FORBIDDEN_PERMISSIONS: frozenset[str] = frozenset(
    [
        "NETWORK_ACCESS",
        "PYTHON_EXECUTION",
        "MCP_TOOL_CALL",
        "CODEBASE_MUTATION",
        "BROKER_EXECUTION",
    ]
)


@dataclass
class ToolInput:
    """Generic tool input container."""

    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutput:
    """Generic tool output container."""

    data: Any = None
    summary: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ToolSpec:
    """Specification for a local Phase 5.8 research tool."""

    name: str
    description: str
    permission: ToolPermission
    # Optional human-readable input/output field descriptions
    input_fields: dict[str, str] = field(default_factory=dict)
    output_fields: dict[str, str] = field(default_factory=dict)
