from __future__ import annotations

import duckdb

from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.tools.executor import TracedLocalToolExecutor
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.migrations import run_migrations


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


def test_research_plan_command_renders_validated_research_blocks() -> None:
    conn = _connection()
    registry = build_default_registry()
    executor = TracedLocalToolExecutor(
        conn,
        build_local_tool_registry(conn),
        session_id="scenario-command-test",
    )

    result = registry.execute(
        parse("/research-plan FPT --date 2025-01-31"),
        conn=conn,
        tool_executor=executor,
    )

    assert result.status.value in {"SUCCESS", "PARTIAL"}
    assert {
        "Current Setup",
        "Key Levels",
        "Conditions",
        "Scenario Tree",
        "Research Estimate",
        "Checklist",
        "Caveats",
    } <= {panel.title for panel in result.panels}


def test_research_plan_command_uses_its_research_session_as_correlation_id() -> None:
    conn = _connection()
    result = CommandExecutor(conn).execute("/research-plan FPT --date 2025-01-31")
    assert result.status.value in {"SUCCESS", "PARTIAL"}
    session_id = conn.execute("SELECT session_id FROM research_session").fetchone()[0]
    correlation_id = conn.execute(
        "SELECT correlation_id FROM research_scenario_plan"
    ).fetchone()[0]
    assert correlation_id == session_id
