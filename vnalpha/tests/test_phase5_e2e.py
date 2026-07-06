"""Phase 5 end-to-end fixture test.

Tests the full pipeline without network access:
migrations → fixture load → canonical → features → score → watchlist
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

import duckdb
import pytest

from vnalpha.core.types import CANONICAL_CANDIDATE_CLASSES, CANONICAL_SETUP_TYPES
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
    get_watchlist_rich,
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

    # Insert VNINDEX benchmark: 130 bars, "up" trend
    vnindex_run_id = create_ingestion_run(conn, "fixture", "/fixture/vnindex")
    vnindex_rows = make_ohlcv_rows("VNINDEX", n_bars=130, base_price=1200.0, trend="up")
    insert_raw_ohlcv(
        conn,
        vnindex_run_id,
        "VNINDEX",
        vnindex_rows,
        provider="fixture",
        quality_status="pass",
    )
    finish_ingestion_run(conn, vnindex_run_id, status="SUCCESS")

    # Insert FPT: strong up trend, 130 bars
    fpt_run_id = create_ingestion_run(conn, "fixture", "/fixture/fpt")
    fpt_rows = make_ohlcv_rows("FPT", n_bars=130, base_price=100.0, trend="strong_up")
    insert_raw_ohlcv(
        conn, fpt_run_id, "FPT", fpt_rows, provider="fixture", quality_status="pass"
    )
    finish_ingestion_run(conn, fpt_run_id, status="SUCCESS")

    # Insert VNM: flat trend, 130 bars
    vnm_run_id = create_ingestion_run(conn, "fixture", "/fixture/vnm")
    vnm_rows = make_ohlcv_rows("VNM", n_bars=130, base_price=80.0, trend="flat")
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


class TestMigrations:
    def test_migrations_create_all_tables(self):
        """All 8 tables must exist after run_migrations."""
        conn = duckdb.connect(":memory:")
        run_migrations(conn=conn)
        expected_tables = {
            "ingestion_run",
            "symbol_master",
            "market_ohlcv_raw",
            "canonical_ohlcv",
            "feature_snapshot",
            "candidate_score",
            "daily_watchlist",
            "rejected_symbol",
        }
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        actual = {r[0] for r in rows}
        missing = expected_tables - actual
        assert not missing, f"Tables missing after migrations: {missing}"
        conn.close()


class TestCanonicalOHLCV:
    def test_canonical_ohlcv_builds_from_raw(self, pipeline_conn):
        """After build_canonical_ohlcv, canonical_ohlcv has rows for FPT."""
        count = pipeline_conn.execute(
            "SELECT COUNT(*) FROM canonical_ohlcv WHERE symbol = 'FPT'"
        ).fetchone()[0]
        assert count > 0, "canonical_ohlcv has no rows for FPT"

    def test_canonical_dedup_prefers_pass_quality(self):
        """Dedup: when two raw rows exist for same (symbol, time, interval),
        canonical picks the one with quality_status='pass'."""
        conn = duckdb.connect(":memory:")
        run_migrations(conn=conn)

        run_id_a = create_ingestion_run(conn, "fixture", "/a")
        run_id_b = create_ingestion_run(conn, "fixture", "/b")

        # Insert two rows for same (symbol, time, interval) — one pass, one fail
        same_time = "2024-01-05"
        conn.execute(
            """
            INSERT INTO market_ohlcv_raw
            (ingestion_run_id, symbol, time, interval, open, high, low, close, volume,
             provider, quality_status, fetched_at)
            VALUES (?, 'DEDUP', ?, '1D', 10.0, 11.0, 9.0, 10.5, 500000, 'prov_a', 'fail', '2024-01-06 00:00:00')
            """,
            [run_id_a, same_time],
        )
        conn.execute(
            """
            INSERT INTO market_ohlcv_raw
            (ingestion_run_id, symbol, time, interval, open, high, low, close, volume,
             provider, quality_status, fetched_at)
            VALUES (?, 'DEDUP', ?, '1D', 10.0, 11.0, 9.0, 99.9, 500000, 'prov_b', 'pass', '2024-01-05 00:00:00')
            """,
            [run_id_b, same_time],
        )

        build_canonical_ohlcv(conn)

        row = conn.execute(
            "SELECT close, quality_status FROM canonical_ohlcv WHERE symbol = 'DEDUP'"
        ).fetchone()
        assert row is not None, "No canonical row for DEDUP"
        assert row[1] == "pass", f"Expected quality_status='pass', got {row[1]!r}"
        assert row[0] == 99.9, f"Expected close=99.9 (pass row), got {row[0]}"
        conn.close()


class TestFeatures:
    def test_features_build_with_benchmark(self, pipeline_conn):
        """FPT feature_snapshot should have rs_20d_vs_vnindex that is not NULL."""
        row = pipeline_conn.execute(
            "SELECT rs_20d_vs_vnindex FROM feature_snapshot WHERE symbol = 'FPT' AND date = ?",
            [TARGET_DATE],
        ).fetchone()
        assert row is not None, "No feature_snapshot row for FPT"
        assert row[0] is not None, (
            "rs_20d_vs_vnindex is NULL for FPT (benchmark not used)"
        )

    def test_features_skips_insufficient_history(self):
        """BAD symbol with only 15 bars should be skipped (built=0, skipped>=1)."""
        conn = duckdb.connect(":memory:")
        run_migrations(conn=conn)

        run_id = create_ingestion_run(conn, "fixture", "/bad_only")
        upsert_symbol(conn, "BAD2")
        bad_rows = make_ohlcv_rows("BAD2", n_bars=15, base_price=50.0, trend="poor")
        insert_raw_ohlcv(
            conn, run_id, "BAD2", bad_rows, provider="fixture", quality_status="pass"
        )
        finish_ingestion_run(conn, run_id, status="SUCCESS")

        build_canonical_ohlcv(conn, symbol="BAD2")
        result = build_features(conn, target_date=TARGET_DATE, universe=["BAD2"])

        assert result["built"] == 0, f"Expected built=0, got {result['built']}"
        assert result["skipped"] >= 1, f"Expected skipped>=1, got {result['skipped']}"
        conn.close()


class TestScoring:
    def test_score_universe_persists_candidate_scores(self, pipeline_conn):
        """candidate_score must have rows for FPT and VNM after score_universe."""
        for sym in ["FPT", "VNM"]:
            row = pipeline_conn.execute(
                "SELECT score FROM candidate_score WHERE symbol = ? AND date = ?",
                [sym, TARGET_DATE],
            ).fetchone()
            assert row is not None, f"No candidate_score row for {sym}"

    def test_canonical_classes_are_canonical(self, pipeline_conn):
        """All persisted candidate_class values must be in CANONICAL_CANDIDATE_CLASSES."""
        rows = pipeline_conn.execute(
            "SELECT DISTINCT candidate_class FROM candidate_score"
        ).fetchall()
        for (cc,) in rows:
            assert cc in CANONICAL_CANDIDATE_CLASSES, (
                f"Non-canonical candidate_class: {cc!r}"
            )

    def test_setup_types_are_canonical(self, pipeline_conn):
        """All persisted setup_type values (when non-null) must be in CANONICAL_SETUP_TYPES."""
        rows = pipeline_conn.execute(
            "SELECT DISTINCT setup_type FROM candidate_score WHERE setup_type IS NOT NULL"
        ).fetchall()
        for (st,) in rows:
            assert st in CANONICAL_SETUP_TYPES, f"Non-canonical setup_type: {st!r}"


class TestWatchlist:
    def test_watchlist_excludes_ignore(self, pipeline_conn):
        """daily_watchlist must have no rows where candidate_class == 'IGNORE'."""
        rows = pipeline_conn.execute(
            "SELECT symbol, candidate_class FROM daily_watchlist WHERE date = ?",
            [TARGET_DATE],
        ).fetchall()
        for sym, cc in rows:
            assert cc != "IGNORE", (
                f"Symbol {sym} in watchlist with candidate_class='IGNORE' — should be excluded"
            )

    def test_watchlist_rich_has_all_required_fields(self, pipeline_conn):
        """get_watchlist_rich returns rows with all Phase 5 required fields."""
        required_fields = {
            "rank",
            "symbol",
            "score",
            "candidate_class",
            "setup_type",
            "evidence_json",
            "risk_flags_json",
            "lineage_json",
            "data_quality_status",
        }
        rows = get_watchlist_rich(pipeline_conn, TARGET_DATE)
        # If watchlist is non-empty, verify fields
        if rows:
            for row in rows:
                missing = required_fields - set(row.keys())
                assert not missing, f"Missing fields in watchlist_rich row: {missing}"

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


class TestDataQuality:
    def test_poor_quality_symbol_rejected_or_skipped(self, pipeline_conn):
        """BAD symbol (15 bars) should not appear in feature_snapshot for TARGET_DATE,
        OR should be in rejected_symbol table."""
        in_features = pipeline_conn.execute(
            "SELECT COUNT(*) FROM feature_snapshot WHERE symbol = 'BAD' AND date = ?",
            [TARGET_DATE],
        ).fetchone()[0]
        in_rejected = pipeline_conn.execute(
            "SELECT COUNT(*) FROM rejected_symbol WHERE symbol = 'BAD'"
        ).fetchone()[0]
        # Either skipped from features (not built) OR flagged in rejected_symbol
        assert in_features == 0 or in_rejected > 0, (
            "BAD symbol (insufficient history) was neither skipped from features "
            "nor logged in rejected_symbol"
        )

    def test_no_network_access(self, pipeline_conn):
        """All fixture data was inserted directly — no HTTP calls needed.
        Verify the ingestion_run rows used 'fixture' as source_service."""
        rows = pipeline_conn.execute(
            "SELECT DISTINCT source_service FROM ingestion_run"
        ).fetchall()
        services = {r[0] for r in rows}
        # All runs in this pipeline should be fixture runs, not live service calls
        assert services == {"fixture"}, (
            f"Unexpected source_service values: {services}. "
            "Tests should only use in-memory fixture data."
        )
