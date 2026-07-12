from __future__ import annotations

from enum import Enum

from vnalpha.assistant.tool_policy import (
    APPROVAL_REQUIRED_TOOLS,
    is_forbidden_tool,
    is_safe_tool,
)
from vnalpha.chat.modes import ExecutionMode


class PermissionState(str, Enum):
    """Canonical permission states for tool/action evaluation.

    - ALLOW:      Safe read-only research tool; execute immediately.
    - ASK:        Potentially side-effecting tool; require explicit approval.
    - DENY:       Not permitted in current execution mode.
    - HARD_DENY:  Permanently forbidden; reject regardless of mode or prompt text.
    """

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"
    HARD_DENY = "hard_deny"


def is_tool_allowed_in_chat(tool_name: str) -> bool:
    """Return the canonical policy decision for a chat tool."""
    return is_safe_tool(tool_name)


def validate_tool_call(
    tool_name: str,
    execution_mode: ExecutionMode,
) -> tuple[bool, str | None]:
    if not is_safe_tool(tool_name):
        return False, f"Tool '{tool_name}' is not available in research chat"
    return True, None


def filter_safe_tools(tool_names: list[str]) -> list[str]:
    return [name for name in tool_names if is_tool_allowed_in_chat(name)]


def get_permission_state(
    tool_name: str, execution_mode: ExecutionMode
) -> PermissionState:
    if is_safe_tool(tool_name):
        return PermissionState.ALLOW
    if tool_name in APPROVAL_REQUIRED_TOOLS:
        return PermissionState.ASK
    if is_forbidden_tool(tool_name):
        return PermissionState.HARD_DENY
    return PermissionState.DENY
