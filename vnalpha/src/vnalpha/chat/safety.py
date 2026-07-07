from __future__ import annotations

from vnalpha.chat.modes import ExecutionMode

DISALLOWED_TOOL_PREFIXES: frozenset[str] = frozenset(
    {
        "broker",
        "order",
        "allocation",
        "account",
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
