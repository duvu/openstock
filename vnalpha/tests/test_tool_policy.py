from __future__ import annotations

import pytest

from vnalpha.assistant.errors import ToolExecutionError
from vnalpha.assistant.models import ToolPlanStep
from vnalpha.assistant.tool_policy import (
    assert_safe_tool,
)

SAFE_TOOL_NAMES = frozenset(
    {
        "watchlist.scan",
        "watchlist.filter",
        "candidate.compare",
        "candidate.explain",
        "quality.get_status",
        "quality.get_many_status",
        "lineage.get_symbol_lineage",
        "history.list_sessions",
        "note.create",
        "market.get_regime",
        "sector.get_strength",
        "sector.get_symbol_alignment",
    }
)

REQUIRED_FORBIDDEN_PREFIXES = (
    "broker",
    "order",
    "allocation",
    "account",
    "trading",
    "margin",
    "transfer",
    "portfolio",
)

REQUIRED_FORBIDDEN_NAMES = frozenset(
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
    }
)


def _step(tool_name: str) -> ToolPlanStep:
    return ToolPlanStep(
        step_id="step_1",
        tool_name=tool_name,
        arguments={},
        purpose="test",
        required_permission="READ_WATCHLIST",
    )


def test_assert_safe_tool_when_unknown_tool() -> None:
    # Given: an unknown assistant tool
    # When: execution safety is asserted
    # Then: a typed execution error prevents use
    with pytest.raises(ToolExecutionError, match="not allowed"):
        assert_safe_tool("unknown.tool")
