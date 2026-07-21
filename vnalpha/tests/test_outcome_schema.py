"""Tests for Phase 6 outcome schema migrations and repo helpers."""

import pytest

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
