from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import duckdb
import pytest

from vnalpha.tools.research_intelligence import (
    deep_symbol_analysis,
    generate_research_scenario,
    generate_shortlist,
    get_setup_history,
    summarize_watchlist_deep,
)
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import save_candidate_score, upsert_symbol


TARGET_DATE = "2026-07-01"


@pytest.fixture
def conn():
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    _seed_research_context(connection)
    yield connection
    connection.close()


def _seed_research_context(conn) -> None:
    upsert_symbol(
        conn,
        "FPT",
        exchange="HOSE",
        name="FPT Corporation",
        sector="Technology",
        industry="Software",
    )
    start = date.fromisoformat(TARGET_DATE) - timedelta(days=59)
    for offset in range(60):
        bar_date = start + timedelta(days=offset)
        close = 100.0 + offset * 0.5
        conn.execute(
            """
            INSERT INTO canonical_ohlcv (
                symbol, time, interval, open, high, low, close, volume,
                selected_provider, quality_status, ingestion_run_id
            ) VALUES (?, ?, '1D', ?, ?, ?, ?, ?, 'test-provider', 'READY', NULL)
            """,
            [
                "FPT",
                datetime.combine(bar_date, datetime.min.time()),
                close - 0.5,
                close + 1.0,
                close - 1.0,
                close,
                1_000_000 + offset * 1_000,
            ],
        )
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, ma100, ma20_slope, ma50_slope,
            volume_ma20, volume_ratio, atr14, return_20d, return_60d,
            rs_20d_vs_vnindex, rs_60d_vs_vnindex, distance_to_ma20,
            distance_to_52w_high, base_range_30d, close_strength,
            volatility_20d, as_of_bar_date, benchmark_as_of_bar_date,
            source_row_count, benchmark_row_count, feature_data_status,
            feature_build_version, feature_generated_at, lineage_json
        ) VALUES (
            'FPT', ?, 129.5, 124.0, 118.0, 110.0, 0.01, 0.008,
            1000000, 1.4, 2.5, 0.08, 0.18, 0.04, 0.10, 0.044,
            -0.03, 0.08, 0.75, 0.02, ?, ?, 60, 60, 'READY',
            'test-v1', ?, ?
        )
        """,
        [
            TARGET_DATE,
            TARGET_DATE,
            TARGET_DATE,
            datetime.now(timezone.utc),
            json.dumps({"source": "test"}),
        ],
    )
    save_candidate_score(
        conn,
        "FPT",
        TARGET_DATE,
        {
            "score": 0.82,
            "candidate_class": "STRONG_CANDIDATE",
            "setup_type": "ACCUMULATION_BASE",
            "trend_score": 0.85,
            "relative_strength_score": 0.78,
            "volume_score": 0.70,
            "base_score": 0.80,
            "breakout_score": 0.72,
            "risk_quality_score": 0.88,
            "risk_flags": [],
            "as_of_bar_date": TARGET_DATE,
            "feature_build_version": "test-v1",
            "source_quality_status": "READY",
        },
    )
    conn.execute(
        """
        INSERT INTO daily_watchlist (
            date, rank, symbol, score, candidate_class, setup_type,
            risk_flags_json, lineage_json
        ) VALUES (?, 1, 'FPT', 0.82, 'STRONG_CANDIDATE',
                  'ACCUMULATION_BASE', '[]', '{}')
        """,
        [TARGET_DATE],
    )
    conn.execute(
        """
        INSERT INTO setup_type_performance (
            as_of_date, horizon_sessions, setup_type, candidate_count,
            avg_forward_return, median_forward_return, avg_excess_return,
            hit_rate, failure_rate, avg_max_drawdown, computed_at,
            evaluator_version, metric_policy_version
        ) VALUES (?, 20, 'ACCUMULATION_BASE', 42, 0.07, 0.06, 0.03,
                  0.62, 0.19, -0.08, ?, 'eval-v1', 'policy-v1')
        """,
        [TARGET_DATE, datetime.now(timezone.utc)],
    )


def test_deep_symbol_analysis_returns_structured_grounded_payload(conn) -> None:
    output = deep_symbol_analysis(conn, "fpt", TARGET_DATE)

    assert output.data["status"] == "READY"
    assert output.data["symbol"] == "FPT"
    assert output.data["score_context"]["score"] == pytest.approx(0.82)
    assert output.data["technical_context"]["rs_20d_vs_vnindex"] == pytest.approx(
        0.04
    )
    assert output.data["levels"]["bars_used"] == 60
    assert output.data["levels"]["support_20d"] is not None
    assert output.data["artifact_refs"]
    assert output.data["methodology_version"]


def test_watchlist_deep_summary_groups_persisted_candidates(conn) -> None:
    output = summarize_watchlist_deep(conn, TARGET_DATE)

    assert output.data["candidate_count"] == 1
    assert output.data["class_distribution"] == {"STRONG_CANDIDATE": 1}
    assert output.data["setup_distribution"] == {"ACCUMULATION_BASE": 1}
    assert output.data["sector_clusters"] == {"Technology": 1}
    assert output.data["research_focus"]["high_relative_strength"][0]["symbol"] == "FPT"


def test_shortlist_is_deterministic_and_research_framed(conn) -> None:
    first = generate_shortlist(conn, TARGET_DATE, limit=5)
    second = generate_shortlist(conn, TARGET_DATE, limit=5)

    assert first.data == second.data
    assert first.data["candidates"][0]["symbol"] == "FPT"
    assert first.data["candidates"][0]["research_rank"] == 1
    assert "research" in " ".join(first.data["caveats"]).lower()
    assert first.data["methodology"]["components"]


def test_research_scenario_has_conditional_branches_and_policy_status(conn) -> None:
    output = generate_research_scenario(
        conn,
        symbol="FPT",
        date=TARGET_DATE,
        with_evidence=True,
    )

    assert output.data["policy_status"] == "PASS"
    assert set(output.data["scenarios"]) == {
        "base_case",
        "confirmation_case",
        "failed_confirmation_case",
        "low_quality_drift_case",
    }
    assert output.data["historical_evidence"]["sample_size"] == 42
    assert output.data["monitoring_checklist"]


def test_setup_history_returns_methodology_and_sample_caveat_contract(conn) -> None:
    output = get_setup_history(
        conn,
        setup_type="ACCUMULATION_BASE",
        date=TARGET_DATE,
        horizon=20,
    )

    assert output.data["status"] == "READY"
    assert output.data["sample_size"] == 42
    assert output.data["metrics"]["median_forward_return"] == pytest.approx(0.06)
    assert output.data["methodology_version"]["evaluator_version"] == "eval-v1"
    assert any("not predictions" in caveat for caveat in output.data["caveats"])
