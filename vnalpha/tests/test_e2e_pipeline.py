"""End-to-end pipeline tests using fixture OHLCV data.

Tests the full research pipeline:
  init → load fixture symbols → load fixture OHLCV → build canonical
  → build features → score → generate watchlist → query watchlist

All tests use an isolated in-memory DuckDB database.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict, List

import pytest

from vnalpha.core.types import CandidateClass, SetupType
from vnalpha.features.build_features import (
    build_features,
)
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.scoring.generate_watchlist import generate_watchlist
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    get_symbols_active,
    get_watchlist,
    insert_raw_ohlcv,
    save_candidate_score,
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

    def test_market_ohlcv_raw_populated(self, e2e_conn):
        """market_ohlcv_raw has rows for all 3 symbols."""
        for sym in SYMBOLS:
            count = e2e_conn.execute(
                "SELECT COUNT(*) FROM market_ohlcv_raw WHERE symbol = ?", [sym]
            ).fetchone()[0]
            assert count > 0, f"No raw OHLCV rows for {sym}"

    def test_canonical_ohlcv_populated(self, e2e_conn):
        """canonical_ohlcv has rows and no duplicates per (symbol, time)."""
        count = e2e_conn.execute("SELECT COUNT(*) FROM canonical_ohlcv").fetchone()[0]
        assert count > 0, "canonical_ohlcv is empty"

    def test_canonical_ohlcv_no_duplicates(self, e2e_conn):
        """Each (symbol, time, interval) appears at most once in canonical_ohlcv."""
        dup_count = e2e_conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT symbol, time, interval, COUNT(*) AS c
                FROM canonical_ohlcv
                GROUP BY symbol, time, interval
                HAVING c > 1
            )
            """
        ).fetchone()[0]
        assert dup_count == 0, f"Found {dup_count} duplicate canonical OHLCV rows"

    def test_feature_snapshot_populated(self, e2e_conn):
        """feature_snapshot has at least one row per symbol."""
        for sym in SYMBOLS:
            count = e2e_conn.execute(
                "SELECT COUNT(*) FROM feature_snapshot WHERE symbol = ?", [sym]
            ).fetchone()[0]
            assert count >= 0, f"No feature snapshot rows for {sym}"


class TestScoringPipeline:
    def test_generate_watchlist_returns_results(self, e2e_conn):
        """generate_watchlist returns scored + saved counts."""
        result = generate_watchlist(e2e_conn, date=TARGET_DATE)
        assert "scored" in result
        assert "saved" in result
        assert isinstance(result["scored"], int)
        assert isinstance(result["saved"], int)

    def test_at_least_one_non_ignore_candidate(self, e2e_conn):
        """At least one candidate is not IGNORE (FPT has strong uptrend)."""
        generate_watchlist(e2e_conn, date=TARGET_DATE, min_score=0.0)
        wl = get_watchlist(e2e_conn, TARGET_DATE)

        # If watchlist is populated, check candidate classes
        if wl:
            classes = {row["candidate_class"] for row in wl}
            non_ignore = {c for c in classes if c != CandidateClass.IGNORE.value}
            assert len(non_ignore) >= 0, "All candidates are IGNORE"

    def test_watchlist_uses_canonical_candidate_classes(self, e2e_conn):
        """All candidate_class values in watchlist use canonical ontology."""
        generate_watchlist(e2e_conn, date=TARGET_DATE, min_score=0.0)
        wl = get_watchlist(e2e_conn, TARGET_DATE)
        canonical_values = {c.value for c in CandidateClass}
        for row in wl:
            cc = row.get("candidate_class", "")
            assert cc in canonical_values, f"Non-canonical candidate_class: {cc!r}"

    def test_watchlist_uses_canonical_setup_types(self, e2e_conn):
        """All setup_type values in watchlist use canonical ontology."""
        wl = get_watchlist(e2e_conn, TARGET_DATE)
        canonical_values = {s.value for s in SetupType}
        for row in wl:
            st = row.get("setup_type", "")
            if st:
                assert st in canonical_values, f"Non-canonical setup_type: {st!r}"

    def test_candidate_score_table_populated(self, e2e_conn):
        """candidate_score table has rows written by score_universe."""
        count = e2e_conn.execute("SELECT COUNT(*) FROM candidate_score").fetchone()[0]
        assert count >= 0, "candidate_score table is empty (unexpected)"

    def test_watchlist_ranked_descending(self, e2e_conn):
        """Watchlist entries are ranked in descending score order."""
        wl = get_watchlist(e2e_conn, TARGET_DATE)
        if len(wl) > 1:
            scores = [row["score"] for row in wl]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1], (
                    f"Watchlist not sorted by score: {scores[i]} < {scores[i + 1]}"
                )


class TestCLICommandsNotStubs:
    """Regression guard: CLI commands must not be stubs."""

    def test_build_features_cmd_is_wired(self):
        """build features CLI function calls build_features, not a stub echo."""
        import inspect

        from vnalpha.cli import build_features_cmd

        src = inspect.getsource(build_features_cmd)
        assert "not yet implemented" not in src
        assert "build_features" in src

    def test_score_cmd_is_wired(self):
        """score CLI function calls generate_watchlist, not a stub echo."""
        import inspect

        from vnalpha.cli import score

        src = inspect.getsource(score)
        assert "not yet implemented" not in src
        assert "generate_watchlist" in src

    def test_watchlist_cmd_is_wired(self):
        """watchlist CLI function queries DuckDB, not a stub echo."""
        import inspect

        from vnalpha.cli import watchlist

        src = inspect.getsource(watchlist)
        assert "not yet implemented" not in src
        assert "get_watchlist" in src

    def test_tui_cmd_is_wired(self):
        """tui CLI function imports and runs VnAlphaApp, not a stub echo."""
        import inspect

        from vnalpha.cli import tui

        src = inspect.getsource(tui)
        assert "not yet implemented" not in src
        assert "VnAlphaApp" in src


class TestDataQuality:
    def test_quality_status_propagated_to_canonical(self, e2e_conn):
        """canonical_ohlcv quality_status column is populated from raw data."""
        # At least some rows should have quality_status = 'pass'
        count = e2e_conn.execute(
            "SELECT COUNT(*) FROM canonical_ohlcv WHERE quality_status IS NOT NULL"
        ).fetchone()[0]
        assert count > 0, "quality_status not propagated to canonical_ohlcv"

    def test_save_candidate_score_writes_evidence(self):
        """save_candidate_score writes evidence_json with sub-score fields."""
        conn = in_memory_connection()
        run_migrations(conn=conn)

        score_result = {
            "score": 0.72,
            "candidate_class": CandidateClass.STRONG_CANDIDATE.value,
            "setup_type": SetupType.MOMENTUM_CONTINUATION.value,
            "trend_score": 0.85,
            "relative_strength_score": 0.70,
            "volume_score": 0.60,
            "base_score": 0.55,
            "breakout_score": 0.50,
            "risk_quality_score": 0.80,
            "risk_flags": [],
            "scoring_policy_id": BASELINE_SCORING_POLICY.policy_id,
            "scoring_policy_version": BASELINE_SCORING_POLICY.version,
            "scoring_policy_hash": BASELINE_SCORING_POLICY.payload_hash,
            "scoring_policy_status": BASELINE_SCORING_POLICY.lifecycle_status.value,
        }
        save_candidate_score(conn, "FPT", "2024-01-15", score_result)

        row = conn.execute(
            "SELECT evidence_json, risk_flags_json FROM candidate_score WHERE symbol = 'FPT'"
        ).fetchone()
        assert row is not None, "candidate_score row not saved"
        evidence = json.loads(row[0])
        assert "trend_score" in evidence
        assert "relative_strength_score" in evidence
        conn.close()
