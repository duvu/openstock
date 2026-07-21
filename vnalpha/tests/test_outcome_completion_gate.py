"""Completion-gate tests for Phase 6 outcome evaluation and reporting."""

from __future__ import annotations

import json
from datetime import date, timedelta

import duckdb
import pytest
from typer.testing import CliRunner

from vnalpha.outcomes.evaluator import evaluate_watchlist_date
from vnalpha.outcomes.repositories import (
    get_candidate_outcomes,
    get_watchlist_outcome,
    list_risk_flag_performance,
    list_score_bucket_performance,
    list_setup_type_performance,
)
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.migrations import run_migrations

runner = CliRunner()


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


def _make_bars(
    start_close: float, n: int, start_date: str = "2026-07-06"
) -> list[dict]:
    d = date.fromisoformat(start_date)
    return [
        {"time": (d + timedelta(days=i)).isoformat(), "close": start_close + i * 0.5}
        for i in range(n)
    ]


def _insert_ohlcv(conn, symbol: str, bars: list[dict]) -> None:
    for bar in bars:
        conn.execute(
            """
            INSERT INTO canonical_ohlcv
                (symbol, time, interval, open, high, low, close, volume)
            VALUES (?, ?, '1D', ?, ?, ?, ?, ?)
            """,
            [
                symbol,
                bar["time"],
                bar["close"],
                bar["close"],
                bar["close"],
                bar["close"],
                1000.0,
            ],
        )


def _insert_watchlist(
    conn, symbol: str, rank: int, score: float, flags: list[str]
) -> None:
    conn.execute(
        """
        INSERT INTO daily_watchlist
            (date, rank, symbol, score, candidate_class, setup_type,
             risk_flags_json, lineage_json, scoring_policy_id,
             scoring_policy_version, scoring_policy_hash, scoring_policy_status)
        VALUES ('2026-07-06', ?, ?, ?, 'STRONG_CANDIDATE',
                'ACCUMULATION_BASE', ?, '{}', ?, ?, ?, ?)
        """,
        [
            rank,
            symbol,
            score,
            json.dumps(flags),
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )


def _seed_complete_outcome_fixture(conn) -> None:
    _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 90))
    _insert_ohlcv(conn, "FPT", _make_bars(100.0, 90))
    _insert_ohlcv(conn, "VNM", _make_bars(80.0, 90))
    _insert_watchlist(conn, "FPT", 1, 0.82, ["THIN_VOLUME"])
    _insert_watchlist(conn, "VNM", 2, 0.65, [])


def test_evaluate_watchlist_date_generates_candidate_and_aggregate_tables(conn):
    _seed_complete_outcome_fixture(conn)

    result = evaluate_watchlist_date(conn, "2026-07-06", horizons=[20])

    assert result["persisted"] == 2
    assert result["aggregates"][20]["watchlist_outcome"] == 2
    assert len(get_candidate_outcomes(conn, "2026-07-06", 20)) == 2
    assert get_watchlist_outcome(conn, "2026-07-06", 20) is not None
    assert list_score_bucket_performance(conn, 20)
    assert list_setup_type_performance(conn, 20)
    assert list_risk_flag_performance(conn, 20)
