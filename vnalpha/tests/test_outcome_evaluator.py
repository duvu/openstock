"""Integration tests for outcome evaluator and aggregations."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from vnalpha.outcomes.evaluator import evaluate_watchlist_date
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


def _make_bars(start_close: float, n: int, start_date: str = "2026-01-01") -> list:
    """Generate n OHLCV-like bars starting at start_date."""
    d = date.fromisoformat(start_date)
    bars = []
    close = start_close
    for i in range(n):
        bars.append({"time": d.isoformat(), "close": close + i * 0.5})
        d += timedelta(days=1)
    return bars


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


def _insert_ohlcv(conn, symbol: str, bars: list) -> None:
    for bar in bars:
        conn.execute(
            """
            INSERT INTO canonical_ohlcv
                (symbol, time, interval, open, high, low, close, volume)
            VALUES (?, ?, '1D', ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, time, interval) DO NOTHING
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
    conn,
    symbol: str,
    watchlist_date: str,
    score: float = 0.75,
    candidate_class: str = "STRONG_CANDIDATE",
    setup_type: str = "ACCUMULATION_BASE",
    risk_flags: list = None,
    rank: int = 1,
) -> None:
    """Insert a daily_watchlist row.

    The real schema uses 'date' (not 'watchlist_date') and PRIMARY KEY (date, rank).
    We use rank as a parameter to allow multiple symbols on the same date.
    """
    conn.execute(
        """
        INSERT INTO daily_watchlist
           (date, rank, symbol, score, candidate_class, setup_type,
            risk_flags_json, lineage_json, scoring_policy_id,
            scoring_policy_version, scoring_policy_hash, scoring_policy_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?, ?)
           ON CONFLICT (date, rank) DO UPDATE SET
               symbol=excluded.symbol,
               score=excluded.score,
               candidate_class=excluded.candidate_class,
               setup_type=excluded.setup_type,
               risk_flags_json=excluded.risk_flags_json,
               lineage_json=excluded.lineage_json,
               scoring_policy_id=excluded.scoring_policy_id,
               scoring_policy_version=excluded.scoring_policy_version,
               scoring_policy_hash=excluded.scoring_policy_hash,
               scoring_policy_status=excluded.scoring_policy_status
        """,
        [
            watchlist_date,
            rank,
            symbol,
            score,
            candidate_class,
            setup_type,
            json.dumps(risk_flags or []),
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )


class TestEvaluatorNoWatchlist:
    def test_no_watchlist_returns_empty(self, conn):
        result = evaluate_watchlist_date(conn, "2026-01-01")
        assert result["evaluated"] == 0
        assert result["persisted"] == 0
