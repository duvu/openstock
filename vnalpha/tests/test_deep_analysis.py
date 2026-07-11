from __future__ import annotations

from typing import get_type_hints

import duckdb

from vnalpha.warehouse.migrations import run_migrations


def _connection() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    return conn


def _seed_analysis_inputs(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, ma100, ma20_slope, ma50_slope,
            volume_ma20, volume_ratio, atr14, return_20d, return_60d,
            rs_20d_vs_vnindex, rs_60d_vs_vnindex, distance_to_ma20,
            distance_to_52w_high, base_range_30d, close_strength, volatility_20d,
            as_of_bar_date, source_row_count, feature_data_status, lineage_json
        ) VALUES (
            'FPT', '2025-01-31', 120.0, 115.0, 108.0, 100.0, 0.02, 0.01,
            1000.0, 1.4, 3.0, 0.08, 0.18, 0.05, 0.12, 0.04,
            -0.03, 0.07, 0.85, 0.18, '2025-01-31', 120, 'EXACT_DATE',
            '{"provider":"KBS","ingestion_run_id":"run-1"}'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO candidate_score (
            symbol, date, score, candidate_class, setup_type, trend_score,
            relative_strength_score, volume_score, base_score, breakout_score,
            risk_quality_score, evidence_json, risk_flags_json, lineage_json
        ) VALUES (
            'FPT', '2025-01-31', 0.82, 'STRONG_CANDIDATE', 'ACCUMULATION_BASE',
            0.8, 0.7, 0.6, 0.5, 0.4, 0.9, '{}', '[]', '{}'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO canonical_ohlcv (
            symbol, time, interval, open, high, low, close, volume,
            selected_provider, quality_status, ingestion_run_id
        ) VALUES
            ('FPT', '2025-01-29', '1D', 112, 116, 110, 114, 900, 'KBS', 'PASS', 'run-1'),
            ('FPT', '2025-01-30', '1D', 114, 119, 113, 118, 1100, 'KBS', 'PASS', 'run-1'),
            ('FPT', '2025-01-31', '1D', 118, 122, 117, 120, 1400, 'KBS', 'PASS', 'run-1')
        """
    )


def test_build_analysis_returns_required_research_blocks_and_persists_artifact() -> (
    None
):
    # Given: a warehouse with deterministic feature, score, and OHLCV inputs
    from vnalpha.research_intelligence.deep_analysis import DeepAnalysisBuilder

    conn = _connection()
    _seed_analysis_inputs(conn)

    # When: a symbol analysis is built as of its feature date
    analysis = DeepAnalysisBuilder(conn).build("FPT", "2025-01-31")

    # Then: every research context block is present without an execution recommendation
    assert analysis["symbol"] == "FPT"
    assert analysis["trend"]["state"] == "UPTREND"
    assert analysis["levels"]["levels"]
    assert set(analysis["setup_quality"]) == {
        "trend_alignment",
        "base_quality",
        "relative_strength_quality",
        "volume_quality",
        "level_quality",
        "risk_penalty",
    }
    assert analysis["scenario"]["monitoring"]
    rendered = str(analysis).lower()
    for forbidden in ("buy", "sell", "order", "allocation", "broker", "margin"):
        assert forbidden not in rendered
    assert conn.execute("SELECT count(*) FROM setup_analysis").fetchone()[0] == 1


def test_deep_analysis_builder_exposes_typed_output_contract() -> None:
    from vnalpha.research_intelligence.deep_analysis import (
        DeepAnalysisBuilder,
        DeepSymbolAnalysis,
    )

    assert get_type_hints(DeepAnalysisBuilder.build)["return"] is DeepSymbolAnalysis


def test_build_analysis_discloses_missing_optional_context() -> None:
    # Given: a warehouse whose feature snapshot lacks benchmark and sector context
    from vnalpha.research_intelligence.deep_analysis import DeepAnalysisBuilder

    conn = _connection()
    _seed_analysis_inputs(conn)
    conn.execute(
        "UPDATE feature_snapshot SET rs_20d_vs_vnindex = NULL, rs_60d_vs_vnindex = NULL WHERE symbol = 'FPT'"
    )

    # When: the analysis is built without optional sector/regime inputs
    analysis = DeepAnalysisBuilder(conn).build("FPT", "2025-01-31")

    # Then: omissions are disclosed rather than inferred or fabricated
    assert "relative strength benchmark data is unavailable" in analysis["missing_data"]
    assert "sector context was not requested" in analysis["missing_data"]


def test_deep_analysis_tool_and_assistant_plan_are_research_only() -> None:
    # Given: the standard local tool registry and assistant planner
    from vnalpha.assistant.models import IntentResult
    from vnalpha.assistant.planner import PlanBuilder
    from vnalpha.tools.setup import build_local_tool_registry

    conn = _connection()

    # When: analysis is exposed to the assistant planning path
    plan = PlanBuilder().build(
        IntentResult(
            intent="deep_analyze_symbol",
            confidence=1.0,
            entities={"symbol": "FPT", "date": "2025-01-31"},
        )
    )

    # Then: it has one read-only local tool step and that tool is registered
    assert [(step.tool_name, step.required_permission) for step in plan.steps] == [
        ("analysis.deep_symbol", "READ_FEATURES")
    ]
    assert "analysis.deep_symbol" in build_local_tool_registry(conn).names()


def test_analyze_command_renders_research_blocks() -> None:
    # Given: a registry with persisted analysis inputs and its local tool executor
    from vnalpha.commands.parser import parse
    from vnalpha.commands.setup import build_default_registry
    from vnalpha.tools.executor import TracedLocalToolExecutor
    from vnalpha.tools.setup import build_local_tool_registry

    conn = _connection()
    _seed_analysis_inputs(conn)
    registry = build_default_registry()
    executor = TracedLocalToolExecutor(
        conn,
        build_local_tool_registry(conn),
        session_id="deep-analysis-test",
    )

    # When: the research-only slash command is executed
    result = registry.execute(
        parse("/analyze FPT --date 2025-01-31"),
        conn=conn,
        registry=registry,
        tool_executor=executor,
    )

    # Then: its output exposes research blocks and caveats, not an order action
    assert result.status == "PARTIAL"
    assert [panel.title for panel in result.panels] == [
        "Trend",
        "Levels",
        "Setup Quality",
        "Scenario",
        "Caveats",
    ]
