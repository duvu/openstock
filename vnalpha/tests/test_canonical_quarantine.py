"""Regression coverage for validation-first canonical OHLCV promotion."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import create_ingestion_run


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    """Provide a migrated in-memory warehouse."""

    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_raw_bar(
    conn: duckdb.DuckDBPyConnection,
    *,
    symbol: str,
    close: float,
    open: float = 10.0,
    high: float = 11.0,
    low: float = 9.0,
    volume: float = 1_000.0,
    provider: str = "fixture",
    quality_status: str = "pass",
    fetched_at: str = "2026-01-06 00:00:00",
    timestamp: str = "2026-01-05",
    interval: str = "1D",
    price_basis: str | None = "RAW_UNADJUSTED",
) -> str:
    """Insert one deterministic raw observation for canonical promotion."""

    run_id = create_ingestion_run(conn, "fixture", "/ohlcv")
    conn.execute(
        """
        INSERT INTO market_ohlcv_raw
            (ingestion_run_id, symbol, time, interval, open, high, low, close,
             volume, provider, price_basis, quality_status, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            symbol,
            timestamp,
            interval,
            open,
            high,
            low,
            close,
            volume,
            provider,
            price_basis,
            quality_status,
            fetched_at,
        ],
    )
    return run_id


def test_invalid_close_is_quarantined_before_canonical_promotion(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """A non-positive close is rejected instead of becoming canonical data."""

    _insert_raw_bar(conn, symbol="BAD", close=0.0)

    result = build_canonical_ohlcv(conn, symbol="BAD")

    canonical_count = conn.execute(
        "SELECT COUNT(*) FROM canonical_ohlcv WHERE symbol = 'BAD'"
    ).fetchone()
    rejection_count = conn.execute(
        "SELECT COUNT(*) FROM rejected_symbol WHERE symbol = 'BAD'"
    ).fetchone()
    assert canonical_count == (0,)
    assert rejection_count == (1,)
    assert result["upserted"] == 0
    assert result["rejected"] == 1


def test_bounded_canonical_promotion_leaves_outside_dates_unchanged(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _insert_raw_bar(conn, symbol="FPT", close=10.0, timestamp="2026-01-05")
    _insert_raw_bar(conn, symbol="FPT", close=11.0, timestamp="2026-01-06")
    build_canonical_ohlcv(conn, symbol="FPT", start="2026-01-05", end="2026-01-05")

    result = build_canonical_ohlcv(
        conn, symbol="FPT", start="2026-01-06", end="2026-01-06"
    )

    rows = conn.execute(
        "SELECT CAST(time AS DATE)::VARCHAR, close FROM canonical_ohlcv "
        "WHERE symbol = 'FPT' ORDER BY time"
    ).fetchall()
    assert rows == [("2026-01-05", 10.0), ("2026-01-06", 11.0)]
    assert result == {"upserted": 1, "rejected": 0}

    _insert_raw_bar(
        conn,
        symbol="VNINDEX",
        close=1_200.0,
        open=1_195.0,
        high=1_201.0,
        low=1_190.0,
        provider="VCI",
        fetched_at="2026-01-06 00:00:00",
    )
    _insert_raw_bar(
        conn,
        symbol="VNINDEX",
        close=1_190.0,
        open=1_185.0,
        high=1_191.0,
        low=1_180.0,
        provider="kbs",
        fetched_at="2026-01-06 01:00:00",
    )

    result = build_canonical_ohlcv(conn, symbol="VNINDEX")

    canonical = conn.execute(
        "SELECT selected_provider, close FROM canonical_ohlcv WHERE symbol = 'VNINDEX'"
    ).fetchall()
    assert canonical == [("VCI", 1_200.0)]
    assert result == {"upserted": 1, "rejected": 0}
