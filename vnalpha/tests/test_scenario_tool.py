from __future__ import annotations

import duckdb

from vnalpha.tools.executor import TracedLocalToolExecutor
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import get_research_scenario_plan


def _connection() -> duckdb.DuckDBPyConnection:
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
    return conn


def test_scenario_tool_generates_a_research_plan() -> None:
    conn = _connection()
    executor = TracedLocalToolExecutor(
        conn,
        build_local_tool_registry(conn),
        session_id="scenario-tool-test",
    )

    output = executor.call(
        "scenario.generate_research_plan",
        symbol="FPT",
        date="2025-01-31",
        correlation_id="scenario-tool-correlation",
    )

    assert output.data["symbol"] == "FPT"
    assert "scenario_tree" in output.data
    assert output.data["correlation_id"] == "scenario-tool-correlation"
    persisted = get_research_scenario_plan(conn, "FPT", "2025-01-31")
    assert persisted is not None
    assert persisted["correlation_id"] == "scenario-tool-correlation"
