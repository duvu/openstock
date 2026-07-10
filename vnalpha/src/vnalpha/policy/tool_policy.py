"""Immutable source-of-truth metadata for local tool capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from vnalpha.policy.permissions import ToolPermission


@dataclass(frozen=True, slots=True)
class ToolCapability:
    """Eligibility and permission metadata for one local tool."""

    name: str
    permission: ToolPermission
    allowed_for_assistant: bool
    allowed_for_command: bool
    allowed_for_autonomous_plan: bool
    mutates_warehouse: bool = False
    requires_confirmation: bool = False


TOOL_CAPABILITIES: Final[tuple[ToolCapability, ...]] = (
    ToolCapability("watchlist.scan", ToolPermission.READ_WATCHLIST, True, True, True),
    ToolCapability("watchlist.filter", ToolPermission.READ_WATCHLIST, True, True, True),
    ToolCapability("candidate.explain", ToolPermission.READ_SCORE, True, True, True),
    ToolCapability("candidate.compare", ToolPermission.READ_SCORE, True, True, True),
    ToolCapability("quality.get_status", ToolPermission.READ_QUALITY, True, True, True),
    ToolCapability(
        "quality.get_many_status", ToolPermission.READ_QUALITY, True, True, True
    ),
    ToolCapability(
        "lineage.get_symbol_lineage", ToolPermission.READ_LINEAGE, True, True, True
    ),
    ToolCapability("note.create", ToolPermission.WRITE_NOTE, True, True, True),
    ToolCapability(
        "history.list_sessions", ToolPermission.READ_HISTORY, True, True, True
    ),
    ToolCapability(
        "data.fetch",
        ToolPermission.WRITE_DATA,
        False,
        True,
        False,
        mutates_warehouse=True,
        requires_confirmation=True,
    ),
)

TOOL_CAPABILITIES_BY_NAME: Final[Mapping[str, ToolCapability]] = MappingProxyType(
    {capability.name: capability for capability in TOOL_CAPABILITIES}
)

TOOL_PERMISSIONS_BY_NAME: Final[Mapping[str, ToolPermission]] = MappingProxyType(
    {capability.name: capability.permission for capability in TOOL_CAPABILITIES}
)
