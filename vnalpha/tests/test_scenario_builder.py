from __future__ import annotations

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


def test_scenario_plan_builder_returns_required_research_fields_and_persists() -> None:
    from vnalpha.research_intelligence.scenario_plan import ScenarioPlanBuilder

    conn = _connection()
    _seed_analysis_inputs(conn)

    plan = ScenarioPlanBuilder(conn).build("FPT", "2025-01-31", correlation_id="corr-1")

    assert {
        "current_setup",
        "key_levels",
        "confirmation_conditions",
        "invalidation_conditions",
        "scenario_tree",
        "risk_reward_estimate",
        "checklist",
        "confidence",
        "caveats",
        "research_only_language",
    } <= set(plan)
    assert set(plan["scenario_tree"]) == {
        "base_case",
        "confirmation_case",
        "failed_confirmation_case",
        "low_quality_drift_case",
    }
    assert set(plan["artifact_references"]) == {
        "deep_analysis",
        "level_snapshot",
        "evidence_snapshot",
    }
    assert plan["correlation_id"] == "corr-1"
    assert (
        conn.execute("SELECT count(*) FROM research_scenario_plan").fetchone()[0] == 1
    )
