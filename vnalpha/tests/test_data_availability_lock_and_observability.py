"""Tests for data_availability lock and observability event emission."""

from __future__ import annotations

from pathlib import Path

import duckdb

from vnalpha.warehouse.migrations import run_migrations


def _fresh_conn():
    conn = duckdb.connect()
    run_migrations(conn=conn)
    return conn


def _insert_symbol(conn, symbol="FPT"):
    conn.execute(
        "INSERT INTO symbol_master (symbol, is_active, last_seen_at) VALUES (?, TRUE, current_timestamp)",
        [symbol],
    )


def _noop_sync_symbols(conn, **kwargs):
    return {"total": 0, "inserted": 0}


def _noop_sync_ohlcv(conn, **kwargs):
    return {"inserted": 0, "skipped": 0}


def _noop_build_canonical(conn, **kwargs):
    return {"upserted": 0, "rejected": 0}


def _noop_build_features(conn, **kwargs):
    return {"built": 0, "skipped": 0}


def _noop_score_universe(conn, **kwargs):
    return 0


class TestEnsureLock:
    """Task 11.1-11.5 — file-based lock per symbol/date."""

    def test_acquire_creates_lock_file(self, tmp_path: Path):
        from vnalpha.data_availability.lock import EnsureLock

        lock = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path)
        assert lock.acquire() is True
        assert lock.lock_path.exists()
        lock.release()
