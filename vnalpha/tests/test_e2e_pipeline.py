"""End-to-end pipeline tests using fixture OHLCV data.

Tests the full research pipeline:
  init → load fixture symbols → load fixture OHLCV → build canonical
  → build features → score → generate watchlist → query watchlist

All tests use an isolated in-memory DuckDB database.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

import pytest

from vnalpha.features.build_features import (
    build_features,
)
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    get_symbols_active,
    insert_raw_ohlcv,
    upsert_symbol,
)

# ---------------------------------------------------------------------------
# Fixture data helpers
# ---------------------------------------------------------------------------

TARGET_DATE = "2024-06-28"
SYMBOLS = ["FPT", "VNM", "HPG"]  # 3 symbols for E2E tests


def _make_ohlcv_rows(
    symbol: str,
    n_days: int = 120,
    base_price: float = 100.0,
    trend: float = 0.001,
) -> List[Dict[str, Any]]:
    """Generate n_days of synthetic daily OHLCV rows for a symbol."""
    rows = []
    start = date(2024, 1, 1)
    price = base_price
    volume_base = 2_000_000.0

    for i in range(n_days):
        d = start + timedelta(days=i)
        price = price * (1.0 + trend + (0.005 if i % 7 == 0 else -0.002))
        close = round(price, 2)
        rows.append(
            {
                "time": str(d),
                "interval": "1D",
                "open": round(close * 0.99, 2),
                "high": round(close * 1.01, 2),
                "low": round(close * 0.98, 2),
                "close": close,
                "volume": volume_base * (1.0 + 0.1 * (i % 5)),
            }
        )
    return rows


def _build_fixture_db():
    """Create a fully-populated in-memory DuckDB with 3 symbols through all pipeline stages."""
    conn = in_memory_connection()
    run_migrations(conn=conn)

    run_id = create_ingestion_run(conn, "vnstock-service", "/v1/reference/symbols")

    # Insert symbols
    symbol_configs = [
        ("FPT", "HOSE", "FPT Corporation", "Technology", "Software"),
        ("VNM", "HOSE", "Vinamilk", "Consumer Staples", "Food & Beverage"),
        ("HPG", "HOSE", "Hoa Phat Group", "Materials", "Steel"),
    ]
    for sym, exch, name, sector, industry in symbol_configs:
        upsert_symbol(
            conn, sym, exchange=exch, name=name, sector=sector, industry=industry
        )

    finish_ingestion_run(conn, run_id, status="SUCCESS")

    # Insert OHLCV for each symbol (FPT with strong uptrend, VNM moderate, HPG weak)
    ohlcv_configs = [
        ("FPT", 120, 100.0, 0.003),  # strong uptrend
        ("VNM", 120, 80.0, 0.0005),  # mild uptrend
        ("HPG", 120, 60.0, -0.001),  # slight downtrend
    ]
    for sym, n, base, trend in ohlcv_configs:
        ohlcv_run_id = create_ingestion_run(conn, "vnstock-service", "/v1/equity/ohlcv")
        rows = _make_ohlcv_rows(sym, n_days=n, base_price=base, trend=trend)
        insert_raw_ohlcv(
            conn, ohlcv_run_id, sym, rows, provider="kbs", quality_status="pass"
        )
        finish_ingestion_run(conn, ohlcv_run_id, status="SUCCESS")

    # Build canonical OHLCV
    build_canonical_ohlcv(conn)

    # Build features
    build_features(conn, target_date=TARGET_DATE)

    return conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def e2e_conn():
    """Shared module-level E2E database fixture."""
    conn = _build_fixture_db()
    yield conn
    conn.close()


class TestWarehouseTables:
    def test_symbol_master_populated(self, e2e_conn):
        """symbol_master has at least the 3 fixture symbols."""
        active = get_symbols_active(e2e_conn)
        for sym in SYMBOLS:
            assert sym in active, f"{sym} not found in symbol_master"
