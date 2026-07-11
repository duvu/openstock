from __future__ import annotations

import duckdb

from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.warehouse.assistant_repo import create_assistant_session
from vnalpha.warehouse.migrations import run_migrations


def test_assistant_scenario_plan_uses_its_assistant_session_as_correlation_id() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, feature_data_status, lineage_json
        ) VALUES ('FPT', '2025-01-31', 120.0, 115.0, 'EXACT_DATE', '{}')
        """
    )
    conn.execute(
        """
        INSERT INTO canonical_ohlcv (
            symbol, time, interval, open, high, low, close, volume
        ) VALUES
            ('FPT', '2025-01-30', '1D', 114, 119, 113, 118, 1100),
            ('FPT', '2025-01-31', '1D', 118, 122, 117, 120, 1400)
        """
    )
    session_id = create_assistant_session(
        conn, surface="test", user_prompt="Create a scenario plan."
    )
    plan = AssistantPlan(
        intent="generate_research_scenario",
        steps=[
            ToolPlanStep(
                step_id="scenario",
                tool_name="scenario.generate_research_plan",
                arguments={"symbol": "FPT", "date": "2025-01-31"},
                purpose="Build a research scenario plan.",
                required_permission="READ_FEATURES",
            )
        ],
    )

    results = AssistantExecutor(conn, assistant_session_id=session_id).execute(plan)

    assert results["scenario"]["data"]["correlation_id"] == session_id
    correlation_id = conn.execute(
        "SELECT correlation_id FROM research_scenario_plan"
    ).fetchone()[0]
    assert correlation_id == session_id
