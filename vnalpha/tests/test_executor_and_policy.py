"""Tests for Phase 5.9 AssistantExecutor and safety/refusal policy."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.assistant.errors import RefusalError
from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.assistant.policy import check_policy
from vnalpha.warehouse.migrations import run_migrations

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


@pytest.fixture
def session_id(conn):
    from vnalpha.warehouse.assistant_repo import create_assistant_session

    return create_assistant_session(conn, surface="test", user_prompt="test prompt")


@pytest.fixture
def executor(conn, session_id):
    return AssistantExecutor(conn, assistant_session_id=session_id)


def _make_plan(*steps: ToolPlanStep, refusal_reason=None) -> AssistantPlan:
    return AssistantPlan(
        intent="scan_candidates",
        steps=list(steps),
        refusal_reason=refusal_reason,
    )


def _make_step(
    tool_name: str, arguments: dict, step_id: str = "step_1"
) -> ToolPlanStep:
    return ToolPlanStep(
        step_id=step_id,
        tool_name=tool_name,
        arguments=arguments,
        purpose="test",
        required_permission="READ_WATCHLIST",
    )


# ===========================================================================
# Policy tests
# ===========================================================================


class TestCheckPolicy:
    def test_policy_refuses_buy(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Buy FPT now")
        assert exc_info.value.policy_category == "TRADING_EXECUTION"


# ===========================================================================
# Executor tests
# ===========================================================================
