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
    state = get_permission_state(tool_name, execution_mode)
    if state == PermissionState.ALLOW:
        return True, None
    if state == PermissionState.ASK:
        if execution_mode == ExecutionMode.PLAN_THEN_APPROVE:
            return True, None
        return (
            False,
            f"Tool '{tool_name}' requires explicit approval in this execution mode.",
        )
    if state == PermissionState.HARD_DENY:
        return (
            False,
            f"Tool '{tool_name}' is permanently forbidden by policy in this workspace.",
        )
    return False, f"Tool '{tool_name}' is not available in research chat in this mode."


def is_tool_approval_pending_eligible(
    tool_name: str, execution_mode: ExecutionMode
) -> bool:
    """Return whether an ASK tool may be retained pending explicit approval."""
    return get_permission_state(tool_name, execution_mode) == PermissionState.ASK and (
        execution_mode
        in (
            ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS,
            ExecutionMode.PLAN_THEN_APPROVE,
        )
    )


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
