"""Tests for Phase 6 outcome schema migrations and repo helpers."""

import pytest

from vnalpha.outcomes.models import (
    DEFAULT_HORIZONS,
    CandidateOutcomeRecord,
    OutcomeStatus,
    RiskFlagPerformanceRecord,
    ScoreBucketPerformanceRecord,
    SetupTypePerformanceRecord,
    WatchlistOutcomeRecord,
    assign_score_bucket,
)
from vnalpha.outcomes.repositories import (
    get_candidate_outcomes,
    get_watchlist_outcome,
    list_risk_flag_performance,
    list_score_bucket_performance,
    list_setup_type_performance,
    upsert_candidate_outcome,
    upsert_risk_flag_performance,
    upsert_score_bucket_performance,
    upsert_setup_type_performance,
    upsert_watchlist_outcome,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

OUTCOME_TABLES = {
    "outcome_evaluation_run",
    "candidate_outcome",
    "watchlist_outcome",
    "score_bucket_performance",
    "setup_type_performance",
    "risk_flag_performance",
}
PHASE5_TABLES = {
    "ingestion_run",
    "symbol_master",
    "market_ohlcv_raw",
    "canonical_ohlcv",
    "feature_snapshot",
    "candidate_score",
    "daily_watchlist",
    "rejected_symbol",
}


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


class TestMigrations:
    def test_all_outcome_tables_created(self, conn):
        tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
        assert OUTCOME_TABLES <= tables

    def test_phase5_tables_unchanged(self, conn):
        tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
        assert PHASE5_TABLES <= tables

    def test_total_table_count(self, conn):
        tables = conn.execute("SHOW TABLES").fetchall()
        # 63 core + ledger (#252) + fundamental_fact (#257) + valuation_snapshot (#258).
        assert len(tables) == 67

    def test_migrations_idempotent(self, conn):
        run_migrations(conn=conn)
        tables = conn.execute("SHOW TABLES").fetchall()
        assert len(tables) == 67


class TestOutcomeModels:
    def test_outcome_status_values(self):
        assert OutcomeStatus.COMPLETE.value == "COMPLETE"
        assert OutcomeStatus.PENDING.value == "PENDING"
        assert OutcomeStatus.PARTIAL.value == "PARTIAL"
        assert OutcomeStatus.MISSING_DATA.value == "MISSING_DATA"
        assert OutcomeStatus.ERROR.value == "ERROR"

    def test_default_horizons(self):
        assert DEFAULT_HORIZONS == [5, 10, 20, 60]

    def test_assign_score_bucket(self):
        assert assign_score_bucket(0.95) == "0.90-1.00"
        assert assign_score_bucket(0.85) == "0.80-0.90"
        assert assign_score_bucket(0.75) == "0.70-0.80"
        assert assign_score_bucket(0.65) == "0.60-0.70"
        assert assign_score_bucket(0.55) == "0.50-0.60"
        assert assign_score_bucket(0.45) == "0.40-0.50"
        assert assign_score_bucket(0.30) == "0.00-0.40"
        assert assign_score_bucket(None) == "0.00-0.40"


class TestCandidateOutcomeRepo:
    def test_upsert_and_get(self, conn):
        rec = CandidateOutcomeRecord(
            symbol="FPT",
            watchlist_date="2026-07-01",
            horizon_sessions=20,
            score=0.75,
            outcome_status=OutcomeStatus.COMPLETE.value,
            forward_return=0.10,
        )
        upsert_candidate_outcome(conn, rec)
        rows = get_candidate_outcomes(conn, "2026-07-01", 20)
        assert len(rows) == 1
        assert rows[0]["symbol"] == "FPT"
        assert rows[0]["forward_return"] == pytest.approx(0.10)

    def test_upsert_updates_existing(self, conn):
        rec = CandidateOutcomeRecord(
            symbol="FPT",
            watchlist_date="2026-07-01",
            horizon_sessions=20,
            outcome_status=OutcomeStatus.PENDING.value,
        )
        upsert_candidate_outcome(conn, rec)
        rec.outcome_status = OutcomeStatus.COMPLETE.value
        rec.forward_return = 0.05
        upsert_candidate_outcome(conn, rec)
        rows = get_candidate_outcomes(conn, "2026-07-01", 20)
        assert rows[0]["outcome_status"] == "COMPLETE"
        assert rows[0]["forward_return"] == pytest.approx(0.05)

    def test_empty_returns_empty_list(self, conn):
        rows = get_candidate_outcomes(conn, "2026-01-01", 20)
        assert rows == []


class TestWatchlistOutcomeRepo:
    def test_upsert_and_get(self, conn):
        rec = WatchlistOutcomeRecord(
            watchlist_date="2026-07-01",
            horizon_sessions=20,
            candidate_count=5,
            complete_count=4,
            pending_count=1,
            hit_rate=0.6,
            failure_rate=0.2,
        )
        upsert_watchlist_outcome(conn, rec)
        result = get_watchlist_outcome(conn, "2026-07-01", 20)
        assert result is not None
        assert result["candidate_count"] == 5
        assert result["hit_rate"] == pytest.approx(0.6)

    def test_get_missing_returns_none(self, conn):
        assert get_watchlist_outcome(conn, "2020-01-01", 20) is None


class TestScoreBucketRepo:
    def test_upsert_and_list(self, conn):
        rec = ScoreBucketPerformanceRecord(
            as_of_date="2026-07-01",
            horizon_sessions=20,
            score_bucket="0.70-0.80",
            candidate_count=3,
            avg_forward_return=0.08,
            hit_rate=0.67,
        )
        upsert_score_bucket_performance(conn, rec)
        rows = list_score_bucket_performance(conn, 20)
        assert len(rows) == 1
        assert rows[0]["score_bucket"] == "0.70-0.80"


class TestSetupTypeRepo:
    def test_upsert_and_list(self, conn):
        rec = SetupTypePerformanceRecord(
            as_of_date="2026-07-01",
            horizon_sessions=20,
            setup_type="ACCUMULATION_BASE",
            candidate_count=2,
            avg_forward_return=0.06,
        )
        upsert_setup_type_performance(conn, rec)
        rows = list_setup_type_performance(conn, 20)
        assert len(rows) == 1
        assert rows[0]["setup_type"] == "ACCUMULATION_BASE"


class TestRiskFlagRepo:
    def test_upsert_and_list(self, conn):
        rec = RiskFlagPerformanceRecord(
            as_of_date="2026-07-01",
            horizon_sessions=20,
            risk_flag="THIN_VOLUME",
            candidate_count=1,
            avg_forward_return=-0.02,
        )
        upsert_risk_flag_performance(conn, rec)
        rows = list_risk_flag_performance(conn, 20)
        assert len(rows) == 1
        assert rows[0]["risk_flag"] == "THIN_VOLUME"
