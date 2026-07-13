"""Derived command permission metadata."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

from vnalpha.policy.permissions import ToolPermission

COMMAND_PERMISSIONS: Final[Mapping[str, tuple[ToolPermission, ...]]] = MappingProxyType(
    {
        "market-regime": (ToolPermission.READ_FEATURES,),
        "sector-strength": (ToolPermission.READ_FEATURES,),
        "scan": (ToolPermission.READ_WATCHLIST,),
        "analyze": (ToolPermission.READ_SCORE,),
        "watchlist-summary": (ToolPermission.READ_WATCHLIST,),
        "shortlist": (ToolPermission.READ_WATCHLIST,),
        "research-plan": (ToolPermission.READ_SCORE,),
        "setup-evidence": (ToolPermission.READ_HISTORY,),
        "filter": (ToolPermission.READ_SCORE,),
        "compare": (ToolPermission.READ_SCORE,),
        "explain": (
            ToolPermission.READ_SCORE,
            ToolPermission.READ_LINEAGE,
            ToolPermission.READ_QUALITY,
        ),
        "quality": (ToolPermission.READ_QUALITY,),
        "lineage": (ToolPermission.READ_LINEAGE,),
        "note": (ToolPermission.WRITE_NOTE,),
        "memory": (),
        "history": (ToolPermission.READ_HISTORY,),
        "context": (),
        "todo": (),
        "sandbox": (),
        "feature": (),
        "experiment": (),
        "hypothesis": (),
        "pattern": (),
        "model": (),
        "chat": (),
        "help": (),
        "repair": (),
        "validate": (),
        "deploy": (),
    }
)


def permission_names(command_name: str) -> list[str]:
    """Return the string names expected by the command metadata API."""
    return [permission.value for permission in COMMAND_PERMISSIONS[command_name]]
