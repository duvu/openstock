"""Assistant research-boundary deny-list constants."""

from __future__ import annotations

from typing import Final

FORBIDDEN_TOOL_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "network",
        "python",
        "mcp",
        "sql",
        "filesystem",
        "broker",
        "order",
        "allocation",
        "account",
        "trading",
        "margin",
        "transfer",
        "portfolio",
    }
)

FORBIDDEN_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {
        "python_exec",
        "shell_exec",
        "raw_sql",
        "file_read",
        "file_write",
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
    }
)
