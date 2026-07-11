from __future__ import annotations

import duckdb

from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.assistant_repo import create_assistant_session
from vnalpha.warehouse.migrations import run_migrations


RESEARCH_TOOL_NAMES = {
    "analysis.deep_symbol",
    "market.get_regime",
    "sector.get_strength",
    "sector.get_symbol_alignment",
    "watchlist.summarize_deep",
    "shortlist.generate",
    "scenario.generate_research_plan",
    "evidence.get_setup_history",
}


def test_local_registry_exposes_all_bounded_research_tools():
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)

    registry = build_local_tool_registry(conn)

    assert RESEARCH_TOOL_NAMES.issubset(set(registry.names()))
    conn.close()


def test_executor_runs_market_context_plan_with_structured_missing_payload():
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    session_id = create_assistant_session(
        conn,
        surface="test",
        user_prompt="review market regime",
    )
    plan = PlanBuilder().build(
        IntentResult(
            intent="review_market_regime",
            confidence=1.0,
            entities={"date": "2026-07-10"},
        )
    )

    outputs = AssistantExecutor(
        conn,
        assistant_session_id=session_id,
    ).execute(plan)

    output = outputs[plan.steps[0].step_id]
    assert isinstance(output, dict)
    assert isinstance(output["data"], dict)
    assert output["data"]["snapshot"] is None
    assert output["warnings"]

    trace = conn.execute(
        """
        SELECT tool_name, status
        FROM tool_trace
        WHERE assistant_session_id = ?
        """,
        [session_id],
    ).fetchone()
    assert trace == ("market.get_regime", "SUCCESS")
    conn.close()
