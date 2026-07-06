"""Tests for the DuckDB warehouse."""

import pytest

from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    get_symbols_active,
    get_watchlist,
    insert_raw_ohlcv,
    upsert_symbol,
)


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


def test_all_tables_created(conn):
    tables = conn.execute("SHOW TABLES").fetchall()
    names = {t[0] for t in tables}
    expected = {
        "ingestion_run",
        "symbol_master",
        "market_ohlcv_raw",
        "canonical_ohlcv",
        "feature_snapshot",
        "candidate_score",
        "daily_watchlist",
        "rejected_symbol",
        "research_session",
        "tool_trace",
        "research_note",
        "assistant_session",
        "llm_trace",
    }
    assert expected == names


def test_ingestion_run_lifecycle(conn):
    run_id = create_ingestion_run(
        conn, "vnstock-service", "/v1/reference/symbols", "VN30"
    )
    assert len(run_id) == 36  # uuid4
    rows = conn.execute(
        "SELECT status FROM ingestion_run WHERE ingestion_run_id = ?", [run_id]
    ).fetchall()
    assert rows[0][0] == "RUNNING"
    finish_ingestion_run(conn, run_id, "SUCCESS")
    rows = conn.execute(
        "SELECT status FROM ingestion_run WHERE ingestion_run_id = ?", [run_id]
    ).fetchall()
    assert rows[0][0] == "SUCCESS"


def test_upsert_symbol(conn):
    upsert_symbol(conn, "FPT", exchange="HOSE", name="FPT Corp")
    rows = conn.execute("SELECT symbol, exchange, name FROM symbol_master").fetchall()
    assert len(rows) == 1
    assert rows[0] == ("FPT", "HOSE", "FPT Corp")
    # Upsert again with updated name
    upsert_symbol(conn, "FPT", exchange="HOSE", name="FPT Corporation")
    rows = conn.execute(
        "SELECT name FROM symbol_master WHERE symbol = 'FPT'"
    ).fetchall()
    assert rows[0][0] == "FPT Corporation"


def test_get_active_symbols(conn):
    upsert_symbol(conn, "FPT")
    upsert_symbol(conn, "VNM")
    symbols = get_symbols_active(conn)
    assert "FPT" in symbols
    assert "VNM" in symbols


def test_insert_raw_ohlcv(conn):
    # Need an ingestion run first
    run_id = create_ingestion_run(conn, "vnstock-service", "/v1/equity/ohlcv")
    records = [
        {
            "time": "2024-01-02",
            "interval": "1D",
            "open": 90.0,
            "high": 92.0,
            "low": 89.0,
            "close": 91.5,
            "volume": 1000000.0,
        },
    ]
    inserted = insert_raw_ohlcv(
        conn, run_id, "FPT", records, "kbs", "pass", "2024-01-02T09:00:00"
    )
    assert inserted == 1


def test_run_migrations_idempotent(conn):
    """Migrations can be run multiple times safely."""
    run_migrations(conn=conn)  # second run
    tables = conn.execute("SHOW TABLES").fetchall()
    assert len(tables) == 13


def test_get_watchlist_empty(conn):
    result = get_watchlist(conn, "2024-01-02")
    assert result == []
