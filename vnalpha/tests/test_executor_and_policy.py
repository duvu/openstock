"""Tests for Phase 5.9 AssistantExecutor and safety/refusal policy."""
from __future__ import annotations

import duckdb
import pytest

from vnalpha.assistant.errors import RefusalError, ToolExecutionError
from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.models import AssistantPlan, IntentResult, ToolPlanStep
from vnalpha.assistant.policy import check_intent_policy, check_policy
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


def _make_step(tool_name: str, arguments: dict, step_id: str = "step_1") -> ToolPlanStep:
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

    def test_policy_refuses_sell(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Should I sell VNM today?")
        assert exc_info.value.policy_category == "TRADING_EXECUTION"

    def test_policy_refuses_broker(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Connect to broker and place the trade")
        assert exc_info.value.policy_category == "TRADING_EXECUTION"

    def test_policy_refuses_portfolio(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Show me portfolio management options")
        assert exc_info.value.policy_category == "TRADING_EXECUTION"

    def test_policy_refuses_web_search(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Do a web search for FPT news")
        assert exc_info.value.policy_category == "UNAVAILABLE_TOOL"

    def test_policy_refuses_python_code(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Run python code to analyze the data")
        assert exc_info.value.policy_category == "UNAVAILABLE_TOOL"

    def test_policy_refuses_mcp(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Use MCP to fetch external data")
        assert exc_info.value.policy_category == "UNAVAILABLE_TOOL"

    def test_policy_refuses_hide_trace(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Please hide trace of this operation")
        assert exc_info.value.policy_category == "SAFETY_BYPASS"

    def test_policy_refuses_fabricate(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Just fabricate the numbers for now")
        assert exc_info.value.policy_category == "SAFETY_BYPASS"

    def test_policy_refuses_guaranteed_prediction(self):
        with pytest.raises(RefusalError) as exc_info:
            check_policy("Is FPT guaranteed to go up?")
        assert exc_info.value.policy_category == "PREDICTION_CERTAINTY"

    def test_policy_allows_research_question(self):
        """Benign research question should not raise."""
        check_policy("Show strongest candidates today")  # no exception

    def test_policy_allows_explain(self):
        """Explain query about watchlist should not raise."""
        check_policy("Why is FPT in the watchlist?")  # no exception


class TestCheckIntentPolicy:
    def test_intent_policy_refuses_unsupported_intent(self):
        intent_result = IntentResult(
            intent="unsupported_or_unsafe",
            confidence=0.9,
            entities={},
            safety_flags=["TRADING_EXECUTION"],
        )
        with pytest.raises(RefusalError) as exc_info:
            check_intent_policy(intent_result)
        assert exc_info.value.policy_category == "TRADING_EXECUTION"

    def test_intent_policy_refuses_unsupported_no_flags(self):
        """Unsupported intent with no flags defaults to UNSUPPORTED category."""
        intent_result = IntentResult(
            intent="unsupported_or_unsafe",
            confidence=0.7,
            entities={},
            safety_flags=[],
        )
        with pytest.raises(RefusalError) as exc_info:
            check_intent_policy(intent_result)
        assert exc_info.value.policy_category == "UNSUPPORTED"

    def test_intent_policy_allows_supported_intent(self):
        """Supported intents should not raise."""
        intent_result = IntentResult(
            intent="scan_candidates",
            confidence=0.95,
            entities={"date": "2024-01-15"},
        )
        check_intent_policy(intent_result)  # no exception


# ===========================================================================
# Executor tests
# ===========================================================================


class TestExecutorAllowlist:
    def test_executor_allowlist_blocks_unknown_tool(self, executor):
        """Tool not in allowlist must raise ToolExecutionError."""
        step = _make_step("network.fetch", {"url": "http://example.com"})
        plan = _make_plan(step)
        with pytest.raises(ToolExecutionError, match="not in the assistant tool allowlist"):
            executor.execute(plan)

    def test_executor_allowlist_blocks_sql_tool(self, executor):
        """Raw SQL tool must be blocked."""
        step = _make_step("sql.execute", {"query": "SELECT * FROM users"})
        plan = _make_plan(step)
        with pytest.raises(ToolExecutionError):
            executor.execute(plan)


class TestExecutorRefusal:
    def test_executor_refusal_plan_raises_refusal_error(self, executor):
        """Plan with refusal_reason set must raise RefusalError immediately."""
        plan = _make_plan(refusal_reason="This is a trading request.")
        with pytest.raises(RefusalError) as exc_info:
            executor.execute(plan)
        assert "Unsupported" in exc_info.value.reason or "trading" in exc_info.value.reason.lower()

    def test_executor_refusal_plan_category_is_unsupported(self, executor):
        """Refusal plan should use UNSUPPORTED policy category."""
        plan = _make_plan(refusal_reason="Out of scope")
        with pytest.raises(RefusalError) as exc_info:
            executor.execute(plan)
        assert exc_info.value.policy_category == "UNSUPPORTED"

    def test_executor_empty_plan_returns_empty_results(self, executor):
        """Empty plan (no steps) should succeed and return empty dict."""
        plan = _make_plan()
        results = executor.execute(plan)
        assert results == {}


class TestExecutorScanNoData:
    def test_executor_scan_no_data_returns_empty(self, conn, session_id):
        """Scan on empty DB should succeed (ToolOutput with empty data list)."""
        executor = AssistantExecutor(conn, assistant_session_id=session_id)
        step = _make_step("watchlist.scan", {"date": "2024-01-15"})
        plan = _make_plan(step)
        results = executor.execute(plan)
        assert "step_1" in results
        result = results["step_1"]
        # ToolOutput is a dataclass — asdict gives {data: [...], summary: ..., warnings: [...]}
        assert "data" in result
        assert isinstance(result["data"], list)
        assert result["data"] == []  # no data in empty DB


class TestExecutorExplainMissingData:
    def test_executor_explain_missing_data_returns_none(self, conn, session_id):
        """Explain on symbol with no data should return ToolOutput with data=None."""
        executor = AssistantExecutor(conn, assistant_session_id=session_id)
        step = _make_step(
            "candidate.explain",
            {"symbol": "FPT", "date": "2024-01-15"},
        )
        plan = _make_plan(step)
        results = executor.execute(plan)
        assert "step_1" in results
        result = results["step_1"]
        assert result["data"] is None


class TestExecutorPersistsToolTrace:
    def test_executor_persists_tool_trace(self, conn, session_id):
        """After executing a plan step, a tool_trace row should be present."""
        executor = AssistantExecutor(conn, assistant_session_id=session_id)
        step = _make_step("watchlist.scan", {"date": "2024-01-15"})
        plan = _make_plan(step)
        executor.execute(plan)

        rows = conn.execute(
            "SELECT tool_name, status FROM tool_trace WHERE assistant_session_id = ?",
            [session_id],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "watchlist.scan"
        assert rows[0][1] == "SUCCESS"

    def test_executor_assistant_trace_has_null_session_id(self, conn, session_id):
        """Assistant tool traces must have session_id=NULL, not the assistant session id."""
        executor = AssistantExecutor(conn, assistant_session_id=session_id)
        step = _make_step("watchlist.scan", {"date": "2024-01-15"})
        plan = _make_plan(step)
        executor.execute(plan)

        rows = conn.execute(
            "SELECT session_id, assistant_session_id, trace_parent_type FROM tool_trace "
            "WHERE assistant_session_id = ?",
            [session_id],
        ).fetchall()
        assert len(rows) == 1
        row_session_id, row_asst_id, parent_type = rows[0]
        assert row_session_id is None, (
            f"Assistant trace session_id must be NULL, got {row_session_id!r}"
        )
        assert row_asst_id == session_id
        assert parent_type == "assistant"

    def test_executor_persists_failed_trace_on_error(self, conn, session_id):
        """When a tool step raises, a FAILED tool_trace row should be persisted."""
        executor = AssistantExecutor(conn, assistant_session_id=session_id)
        # compare requires 'symbols' and 'date' — pass missing args to trigger error
        step = _make_step("candidate.compare", {"symbols": None, "date": None})
        plan = _make_plan(step)
        with pytest.raises(ToolExecutionError):
            executor.execute(plan)

        rows = conn.execute(
            "SELECT tool_name, status FROM tool_trace WHERE assistant_session_id = ?",
            [session_id],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "FAILED"
