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
from vnalpha.outcomes.evaluator import evaluate_date_range, evaluate_watchlist_date
from vnalpha.outcomes.metrics import CLOSE_ONLY_V1 as METRIC_POLICY_VERSION
from vnalpha.outcomes.models import (
    OUTCOME_EVALUATION_ASSUMPTIONS_CONTRACT_VERSION,
    OUTCOME_EVALUATION_ASSUMPTIONS_HASH,
    OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD_JSON,
    OutcomeStatus,
)
from vnalpha.outcomes.repositories import (
    get_candidate_outcomes,
    get_evaluation_run,
    get_watchlist_outcome,
)
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

    def test_next_session_entry_bases_forward_return_for_benchmark(self, conn):
        conn.execute(
            """
            INSERT INTO canonical_ohlcv
                (symbol, time, interval, open, high, low, close, volume)
            VALUES
                ('FPT', '2026-01-01', '1D', 100, 100, 100, 100, 100),
                ('FPT', '2026-01-02', '1D', 110, 110, 110, 110, 100),
                ('FPT', '2026-01-03', '1D', 120, 120, 120, 120, 100),
                ('VNINDEX', '2026-01-01', '1D', 1000, 1000, 1000, 1000, 100),
                ('VNINDEX', '2026-01-02', '1D', 1100, 1100, 1100, 1100, 100),
                ('VNINDEX', '2026-01-03', '1D', 1200, 1200, 1200, 1200, 100)
            ON CONFLICT (symbol, time, interval) DO NOTHING
            """
        )
        _insert_watchlist(conn, "FPT", "2026-01-01", score=0.80)

        evaluate_watchlist_date(conn, "2026-01-01", horizons=[2])
        rows = get_candidate_outcomes(conn, "2026-01-01", 2)
        assert rows[0]["observation_start_date"] == "2026-01-02"
        assert rows[0]["observation_end_date"] == "2026-01-03"
        assert rows[0]["entry_close"] == 110.0
        assert rows[0]["exit_close"] == 120.0
        assert rows[0]["forward_return"] == pytest.approx(10.0 / 110.0)
        assert rows[0]["benchmark_return"] == pytest.approx(100.0 / 1100.0)

    def test_next_session_entry_bases_forward_return(self, conn):
        conn.execute(
            """
            INSERT INTO canonical_ohlcv
                (symbol, time, interval, open, high, low, close, volume)
            VALUES
                ('FPT', '2026-01-01', '1D', 100, 100, 100, 100, 100),
                ('FPT', '2026-01-02', '1D', 110, 110, 110, 110, 100),
                ('FPT', '2026-01-03', '1D', 120, 120, 120, 120, 100),
                ('VNINDEX', '2026-01-01', '1D', 1000, 1000, 1000, 1000, 100),
                ('VNINDEX', '2026-01-02', '1D', 1100, 1100, 1100, 1100, 100),
                ('VNINDEX', '2026-01-03', '1D', 1200, 1200, 1200, 1200, 100)
            ON CONFLICT (symbol, time, interval) DO NOTHING
            """
        )
        _insert_watchlist(conn, "FPT", "2026-01-01", score=0.80)

        evaluate_watchlist_date(conn, "2026-01-01", horizons=[2])
        rows = get_candidate_outcomes(conn, "2026-01-01", 2)
        assert rows[0]["observation_start_date"] == "2026-01-02"
        assert rows[0]["observation_end_date"] == "2026-01-03"
        assert rows[0]["entry_close"] == 110.0
        assert rows[0]["exit_close"] == 120.0
        assert rows[0]["forward_return"] == pytest.approx(10.0 / 110.0)
        assert rows[0]["benchmark_return"] == pytest.approx(100.0 / 1100.0)

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
                conn,
                sym,
                "2026-01-01",
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


class TestEvaluationRunVersioning:
    """Tests for evaluation run creation and versioning (task 9.6)."""

    def test_evaluate_creates_evaluation_run(self, conn):
        """evaluate_watchlist_date creates and finishes an evaluation_run record."""
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        result = evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        run_id = result["evaluation_run_id"]
        assert run_id is not None

        run = get_evaluation_run(conn, run_id)
        assert run is not None
        assert run["watchlist_date"] == "2026-01-01"
        assert run["status"] == "COMPLETE"
        assert run["evaluated"] == 1
        assert run["persisted"] == 1
        assert run["errors"] == 0

    def test_evaluate_run_has_version_fields(self, conn):
        """Evaluation run stores evaluator and metric policy versions."""
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        result = evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        run = get_evaluation_run(conn, result["evaluation_run_id"])
        assert run["evaluator_version"] is not None
        assert run["metric_policy_version"] == METRIC_POLICY_VERSION

    def test_candidate_outcome_carries_run_id(self, conn):
        """Persisted candidate outcome rows carry evaluation_run_id."""
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        result = evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        run_id = result["evaluation_run_id"]

        row = conn.execute(
            "SELECT evaluation_run_id FROM candidate_outcome WHERE symbol='FPT' AND horizon_sessions=20"
        ).fetchone()
        assert row is not None
        assert row[0] == run_id

    def test_candidate_outcome_carries_metric_policy(self, conn):
        """Candidate outcome rows store metric_policy_version."""
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        row = conn.execute(
            "SELECT metric_policy_version FROM candidate_outcome WHERE symbol='FPT' AND horizon_sessions=20"
        ).fetchone()
        assert row is not None
        assert row[0] == METRIC_POLICY_VERSION

    def test_recomputation_creates_new_run_id(self, conn):
        """Running evaluation twice creates two distinct run IDs."""
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        result1 = evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        result2 = evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        assert result1["evaluation_run_id"] != result2["evaluation_run_id"]

    def test_evaluate_run_stores_symbol_bar_counts(self, conn):
        """Evaluation run records symbol bar counts for audit."""
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        result = evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        run = get_evaluation_run(conn, result["evaluation_run_id"])
        assert run["symbol_bar_count_json"] is not None
        counts = json.loads(run["symbol_bar_count_json"])
        assert "FPT" in counts
        assert counts["FPT"] == 80
        assert run["benchmark_bar_count"] == 80

    def test_evaluate_run_records_assumption_metadata(self, conn):
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        result = evaluate_watchlist_date(conn, "2026-01-01", horizons=[20])
        run = get_evaluation_run(conn, result["evaluation_run_id"])
        assert (
            run["assumptions_contract_version"]
            == OUTCOME_EVALUATION_ASSUMPTIONS_CONTRACT_VERSION
        )
        assert (
            run["assumptions_payload_json"]
            == OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD_JSON
        )
        assert run["assumptions_hash"] == OUTCOME_EVALUATION_ASSUMPTIONS_HASH

    def test_no_watchlist_returns_no_run_id(self, conn):
        """When no watchlist rows, evaluation_run_id is None (no run created)."""
        result = evaluate_watchlist_date(conn, "2026-01-01")
        assert result["evaluation_run_id"] is None


class TestRangeEvaluation:
    """Tests for evaluate_date_range() range semantics and run_id reporting."""

    @pytest.fixture
    def conn(self):
        c = in_memory_connection()
        run_migrations(conn=c)
        yield c
        c.close()

    def test_distinct_run_ids_per_date(self, conn):
        """Each date in a range gets its own evaluation_run_id."""
        for sym_date in ["2026-01-01", "2026-01-02"]:
            bars = _make_bars(100.0, 80, sym_date)
            _insert_ohlcv(conn, "FPT", bars)
            _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, sym_date))
            _insert_watchlist(conn, "FPT", sym_date)

        results = evaluate_date_range(conn, "2026-01-01", "2026-01-02", horizons=[20])
        run_ids = [r["evaluation_run_id"] for r in results if r["evaluation_run_id"]]
        assert len(run_ids) == 2
        assert run_ids[0] != run_ids[1]

    def test_all_results_include_run_id_key(self, conn):
        """All result dicts from evaluate_date_range have evaluation_run_id key."""
        bars = _make_bars(100.0, 80, "2026-01-01")
        _insert_ohlcv(conn, "FPT", bars)
        _insert_ohlcv(conn, "VNINDEX", _make_bars(1200.0, 80, "2026-01-01"))
        _insert_watchlist(conn, "FPT", "2026-01-01")

        results = evaluate_date_range(conn, "2026-01-01", "2026-01-01", horizons=[20])
        assert len(results) == 1
        assert "evaluation_run_id" in results[0]

    def test_empty_date_range_returns_empty_list(self, conn):
        """evaluate_date_range with from_date > to_date returns empty list."""
        results = evaluate_date_range(conn, "2026-01-05", "2026-01-01", horizons=[20])
        assert results == []
