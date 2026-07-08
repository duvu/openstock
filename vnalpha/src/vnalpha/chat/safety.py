from __future__ import annotations

from enum import Enum

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


DISALLOWED_TOOL_PREFIXES: frozenset[str] = frozenset(
    {
        "broker",
        "order",
        "allocation",
        "account",
        "trading",
        "margin",
        "transfer",
    }
)

DISALLOWED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "place_order",
        "cancel_order",
        "modify_order",
        "submit_order",
        "execute_order",
        "get_holdings",
        "rebalance",
        "rebalance_holdings",
        "allocate",
        "allocate_capital",
        "get_account",
        "get_account_balance",
        "transfer_funds",
        "withdraw",
        "deposit",
        "connect_broker",
        "disconnect_broker",
        "authenticate_broker",
        "auto_execute",
        "schedule_trade",
        "automated_execution",
        "run_shell",
        "execute_shell",
        "shell_command",
        "shell_exec",
        "subprocess_run",
        "run_sql",
        "execute_sql",
        "raw_sql",
        "arbitrary_sql",
        "disable_safety",
        "bypass_safety",
        "hide_trace",
        "suppress_trace",
        "ignore_safety_rules",
    }
)

REQUIRES_PLAN_APPROVAL_TOOLS: frozenset[str] = frozenset(
    {
        "execute_python",
        "run_python",
        "eval_code",
        "exec_code",
        "web_fetch",
        "http_get",
        "http_post",
        "fetch_url",
        "mcp_call",
        "mcp_invoke",
        "write_file",
        "delete_file",
        "create_file",
        "append_file",
    }
)


def is_tool_allowed_in_chat(tool_name: str) -> bool:
    if tool_name in DISALLOWED_TOOL_NAMES:
        return False
    for prefix in DISALLOWED_TOOL_PREFIXES:
        if tool_name.startswith(prefix + "_") or tool_name.startswith(prefix + "."):
            return False
        if tool_name == prefix:
            return False
    return True


def requires_plan_approval(tool_name: str) -> bool:
    return tool_name in REQUIRES_PLAN_APPROVAL_TOOLS


def validate_tool_call(
    tool_name: str,
    execution_mode: ExecutionMode,
) -> tuple[bool, str | None]:
    if not is_tool_allowed_in_chat(tool_name):
        return False, f"Tool '{tool_name}' is not available in research chat"

    if (
        requires_plan_approval(tool_name)
        and execution_mode == ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
    ):
        return (
            False,
            (
                f"Tool '{tool_name}' requires plan approval. "
                "Use /plan on or switch to PLAN_THEN_APPROVE mode"
            ),
        )

    return True, None


def filter_safe_tools(tool_names: list[str]) -> list[str]:
    return [name for name in tool_names if is_tool_allowed_in_chat(name)]


def get_permission_state(
    tool_name: str, execution_mode: ExecutionMode
) -> PermissionState:
    if not is_tool_allowed_in_chat(tool_name):
        return PermissionState.HARD_DENY
    if requires_plan_approval(tool_name):
        if execution_mode == ExecutionMode.PLAN_ONLY:
            return PermissionState.ASK
        return PermissionState.ALLOW
    return PermissionState.ALLOW
