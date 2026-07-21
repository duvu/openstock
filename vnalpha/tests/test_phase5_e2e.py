"""Phase 5 end-to-end fixture test.

Tests the full pipeline without network access:
migrations → fixture load → canonical → features → score → watchlist
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

import duckdb
import pytest

from vnalpha.features.build_features import build_features
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.scoring.generate_watchlist import (
    save_watchlist,
    score_universe,
)
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    insert_raw_ohlcv,
    upsert_symbol,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_DATE = "2024-01-10"
START_DATE = date(2023, 8, 1)  # 130 bars from here ends ~2024-01-10


# ---------------------------------------------------------------------------
# OHLCV fixture generator
# ---------------------------------------------------------------------------


def make_ohlcv_rows(
    symbol: str,
    n_bars: int = 130,
    base_price: float = 100.0,
    trend: str = "up",
) -> List[Dict[str, Any]]:
    """Generate n_bars daily OHLCV rows for fixture use.

    trend="up"   → close increases ~0.1% per bar, volume ~1_000_000
    trend="flat" → flat price, lower volume
    trend="poor" → only 15 rows, volume 10_000 (thin — ignored by caller's n_bars arg)
    """
    rows = []
    price = base_price

    if trend == "up":
        multiplier = 1.001
        vol_base = 1_000_000.0
    elif trend == "strong_up":
        multiplier = 1.003
        vol_base = 3_000_000.0
    elif trend == "flat":
        multiplier = 1.0
        vol_base = 200_000.0
    else:  # poor
        multiplier = 1.0
        vol_base = 10_000.0

    for i in range(n_bars):
        d = START_DATE + timedelta(days=i)
        price = price * multiplier
        close = round(price, 2)
        rows.append(
            {
                "time": str(d),
                "interval": "1D",
                "open": round(close * 0.99, 2),
                "high": round(close * 1.01, 2),
                "low": round(close * 0.98, 2),
                "close": close,
                "volume": vol_base * (1.0 + 0.1 * (i % 5)),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Shared module-level pipeline fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pipeline_conn():
    """Run the full Phase 5 pipeline with fixture data."""
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)

    run_id = create_ingestion_run(conn, "fixture", "/fixture/setup")

    # Insert fixture symbols
    for sym in ["VNINDEX", "FPT", "VNM", "BAD"]:
        upsert_symbol(conn, sym, exchange="HOSE", name=sym)

    finish_ingestion_run(conn, run_id, status="SUCCESS")

    vnindex_run_id = create_ingestion_run(conn, "fixture", "/fixture/vnindex")
    vnindex_rows = make_ohlcv_rows("VNINDEX", n_bars=163, base_price=1200.0, trend="up")
    insert_raw_ohlcv(
        conn,
        vnindex_run_id,
        "VNINDEX",
        vnindex_rows,
        provider="fixture",
        quality_status="pass",
    )
    finish_ingestion_run(conn, vnindex_run_id, status="SUCCESS")

    fpt_run_id = create_ingestion_run(conn, "fixture", "/fixture/fpt")
    fpt_rows = make_ohlcv_rows("FPT", n_bars=163, base_price=100.0, trend="strong_up")
    insert_raw_ohlcv(
        conn, fpt_run_id, "FPT", fpt_rows, provider="fixture", quality_status="pass"
    )
    finish_ingestion_run(conn, fpt_run_id, status="SUCCESS")

    vnm_run_id = create_ingestion_run(conn, "fixture", "/fixture/vnm")
    vnm_rows = make_ohlcv_rows("VNM", n_bars=163, base_price=80.0, trend="flat")
    insert_raw_ohlcv(
        conn, vnm_run_id, "VNM", vnm_rows, provider="fixture", quality_status="pass"
    )
    finish_ingestion_run(conn, vnm_run_id, status="SUCCESS")

    # Insert BAD: only 15 bars (insufficient history), plus one row with close=None
    bad_run_id = create_ingestion_run(conn, "fixture", "/fixture/bad")
    bad_rows = make_ohlcv_rows("BAD", n_bars=15, base_price=50.0, trend="poor")
    # Inject a null-close row
    null_row = {
        "time": str(START_DATE + timedelta(days=200)),
        "interval": "1D",
        "open": 50.0,
        "high": 51.0,
        "low": 49.0,
        "close": None,
        "volume": 1000.0,
    }
    bad_rows.append(null_row)
    insert_raw_ohlcv(
        conn, bad_run_id, "BAD", bad_rows, provider="fixture", quality_status="pass"
    )
    finish_ingestion_run(conn, bad_run_id, status="SUCCESS")

    # Build canonical OHLCV
    build_canonical_ohlcv(conn)

    # Build features for TARGET_DATE (universe = FPT, VNM, BAD — not VNINDEX)
    build_features(conn, target_date=TARGET_DATE)

    # Score universe and save watchlist
    score_universe(conn, date=TARGET_DATE)
    save_watchlist(conn, date=TARGET_DATE, min_score=0.0)

    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWatchlist:
    def test_pipeline_produces_at_least_one_noniignore_candidate(self, pipeline_conn):
        """After scoring FPT (strong) and VNM (flat), at least one should not be IGNORE."""
        rows = pipeline_conn.execute(
            "SELECT candidate_class FROM candidate_score WHERE date = ?",
            [TARGET_DATE],
        ).fetchall()
        classes = {r[0] for r in rows}
        non_ignore = classes - {"IGNORE"}
        assert len(non_ignore) >= 1, (
            f"All scored symbols are IGNORE: {classes}. "
            "FPT with strong_up trend should score above IGNORE threshold."
        )
