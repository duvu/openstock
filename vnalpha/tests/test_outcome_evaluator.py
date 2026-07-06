"""Integration tests for outcome evaluator and aggregations."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from vnalpha.outcomes.aggregations import (
    aggregate_all,
    aggregate_risk_flag_performance,
    aggregate_score_bucket_performance,
    aggregate_setup_type_performance,
    aggregate_watchlist_outcome,
)
from vnalpha.outcomes.evaluator import evaluate_watchlist_date
from vnalpha.outcomes.models import OutcomeStatus
from vnalpha.outcomes.repositories import get_candidate_outcomes, get_watchlist_outcome
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
            [symbol, bar["time"], bar["close"], bar["close"], bar["close"], bar["close"], 1000.0],
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
           (date, rank, symbol, score, candidate_class, setup_type, risk_flags_json, lineage_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
           ON CONFLICT (date, rank) DO UPDATE SET
               symbol=excluded.symbol,
               score=excluded.score,
               candidate_class=excluded.candidate_class,
               setup_type=excluded.setup_type,
               risk_flags_json=excluded.risk_flags_json,
               lineage_json=excluded.lineage_json
        """,
        [
            watchlist_date, rank, symbol, score, candidate_class, setup_type,
            json.dumps(risk_flags or []),
        ],
    )


class TestEvaluatorNoWatchlist:
    def test_no_watchlist_returns_empty(self, conn):
        result = evaluate_watchlist_date(conn, "2026-01-01")
        assert result["evaluated"] == 0
        assert result["persisted"] == 0


class TestEvaluatorComplete:
    def test_complete_outcome(self, conn):
        # Insert 80 days of FPT bars (entry on day 0, exit on day 20)
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        # Insert same for VNINDEX benchmark
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        # Watchlist on 2026-01-01
        _insert_watchlist(conn, "FPT", "2026-01-01", score=0.80)

        result = evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        assert result["persisted"] == 1
        assert result["errors"] == 0

        rows = get_candidate_outcomes(conn, "2026-01-01", 20)
        assert len(rows) == 1
        assert rows[0]["outcome_status"] == OutcomeStatus.COMPLETE.value
        assert rows[0]["forward_return"] is not None
        assert rows[0]["excess_return_vs_vnindex"] is not None

    def test_complete_outcome_has_max_gain_and_drawdown(self, conn):
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        rows = get_candidate_outcomes(conn, "2026-01-01", 20)
        assert rows[0]["max_gain"] is not None
        assert rows[0]["max_drawdown"] is not None

    def test_hit_flag_set(self, conn):
        bars = _make_bars(100.0, 80, "2026-01-01")
        # Bench grows slower
        bench_bars = _make_bars(1200.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", bench_bars)
        _insert_watchlist(conn, "FPT", "2026-01-01")

        evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        rows = get_candidate_outcomes(conn, "2026-01-01", 20)
        # Both grow at same rate (0.5 per day), so excess ≈ 0; hit/failure determined by exact values
        # At minimum, hit/failure should be boolean (not None)
        assert rows[0]["hit"] is not None


class TestEvaluatorPending:
    def test_pending_when_insufficient_bars(self, conn):
        # Only 5 bars available, need 20
        bars = _make_bars(100.0, 5, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 5, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        rows = get_candidate_outcomes(conn, "2026-01-01", 20)
        assert rows[0]["outcome_status"] == OutcomeStatus.PENDING.value
        assert rows[0]["required_bars"] == 20


class TestEvaluatorMissingData:
    def test_missing_data_when_no_symbol_ohlcv(self, conn):
        # No OHLCV for FPT
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        rows = get_candidate_outcomes(conn, "2026-01-01", 20)
        assert rows[0]["outcome_status"] == OutcomeStatus.MISSING_DATA.value

    def test_partial_when_no_benchmark(self, conn):
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        # No VNINDEX data
        _insert_watchlist(conn, "FPT", "2026-01-01")

        evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        rows = get_candidate_outcomes(conn, "2026-01-01", 20)
        assert rows[0]["outcome_status"] == OutcomeStatus.PARTIAL.value
        assert rows[0]["forward_return"] is not None
        assert rows[0]["benchmark_return"] is None


class TestAggregations:
    def _setup_complete_outcomes(self, conn, n_candidates: int = 3):
        """Insert n_candidates with complete outcomes for watchlist 2026-01-01, horizon 20."""
        symbols = ["FPT", "VNM", "HPG", "MWG", "VIC"][:n_candidates]
        bars_per_sym = 80
        bench_bars = _make_bars(1200.0, bars_per_sym, "2026-01-01")
        _insert_ohlcv(conn, "VNINDEX", bench_bars)
        for i, sym in enumerate(symbols):
            bars = _make_bars(100.0 + i * 10, bars_per_sym, "2026-01-01")
            _insert_ohlcv(conn, sym, bars)
            _insert_watchlist(
                conn, sym, "2026-01-01",
                score=0.70 + i * 0.05,
                setup_type="ACCUMULATION_BASE",
                risk_flags=["THIN_VOLUME"] if i == 0 else [],
                rank=i + 1,
            )
        evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])

    def test_watchlist_outcome_aggregate(self, conn):
        self._setup_complete_outcomes(conn, 3)
        rec = aggregate_watchlist_outcome(conn, "2026-01-01", 20)
        assert rec.candidate_count == 3
        assert rec.complete_count == 3
        result = get_watchlist_outcome(conn, "2026-01-01", 20)
        assert result is not None
        assert result["candidate_count"] == 3

    def test_score_bucket_aggregate(self, conn):
        self._setup_complete_outcomes(conn, 3)
        recs = aggregate_score_bucket_performance(conn, "2026-01-01", 20)
        assert len(recs) >= 1
        # All scores 0.70-0.80 range
        buckets = {r.score_bucket for r in recs}
        assert "0.70-0.80" in buckets or "0.80-0.90" in buckets

    def test_setup_type_aggregate(self, conn):
        self._setup_complete_outcomes(conn, 3)
        recs = aggregate_setup_type_performance(conn, "2026-01-01", 20)
        assert len(recs) == 1
        assert recs[0].setup_type == "ACCUMULATION_BASE"

    def test_risk_flag_aggregate(self, conn):
        self._setup_complete_outcomes(conn, 3)
        recs = aggregate_risk_flag_performance(conn, "2026-01-01", 20)
        flags = {r.risk_flag for r in recs}
        assert "THIN_VOLUME" in flags

    def test_aggregate_excludes_pending(self, conn):
        # Only 5 bars so all PENDING
        bars = _make_bars(100.0, 5, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 5, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")
        evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])

        rec = aggregate_watchlist_outcome(conn, "2026-01-01", 20)
        assert rec.complete_count == 0
        assert rec.pending_count == 1
        assert rec.avg_forward_return is None  # no complete outcomes

    def test_aggregate_all(self, conn):
        self._setup_complete_outcomes(conn, 2)
        summary = aggregate_all(conn, "2026-01-01", 20)
        assert summary["watchlist_outcome"] == 2
        assert summary["score_buckets"] >= 1
