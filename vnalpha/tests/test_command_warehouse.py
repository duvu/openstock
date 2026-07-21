"""Tests for Phase 5.8 warehouse schema additions and session/note repos (Tasks 4.1-4.6)."""

from __future__ import annotations

import pytest

from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    """In-memory DuckDB connection with all migrations applied."""
    import duckdb

    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


class TestSchemaAdditive:
    def test_phase5_tables_still_exist(self, conn):
        """Phase 5 tables must still be present after Phase 5.8 migration."""
        phase5_tables = [
            "ingestion_run",
            "symbol_master",
            "market_ohlcv_raw",
            "canonical_ohlcv",
            "feature_snapshot",
            "candidate_score",
            "daily_watchlist",
            "rejected_symbol",
        ]
        existing = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        for t in phase5_tables:
            assert t in existing, f"Missing Phase 5 table: {t}"
