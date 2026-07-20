"""Tests for issue #258: derived stock and sector valuation snapshots."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.fundamentals import (
    AuditStatus,
    FundamentalFact,
    StatementScope,
    upsert_fundamental_fact,
)
from vnalpha.valuation import (
    ValuationInputs,
    build_valuation_snapshot,
    compute_valuation_metrics,
    get_valuation_snapshot,
    percentile_rank,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _seed_price(conn, symbol, date, close):
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume,
             selected_provider, price_basis, quality_status)
        VALUES (?, ?, '1D', ?, ?, ?, ?, 1000, 'vci', 'RAW_UNADJUSTED', 'OK')
        """,
        [symbol, f"{date} 00:00:00", close, close, close, close],
    )


def _seed_symbol(conn, symbol, sector_code="TECH"):
    conn.execute(
        "INSERT INTO symbol_master (symbol, sector_code, taxonomy_version, is_active) "
        "VALUES (?, ?, 'icb-2026', TRUE)",
        [symbol, sector_code],
    )
    # Point-in-time sector resolution (#296) reads symbol_classification_history
    # rather than current-state symbol_master, so seed an open-ended history row.
    conn.execute(
        """
        INSERT INTO symbol_classification_history (
            symbol, effective_from, effective_to, source_snapshot_id,
            classification_source, exchange, security_type, lifecycle_status,
            listing_date, delisting_date, sector_code, sector_name,
            industry_code, industry_name, taxonomy_name, taxonomy_version
        ) VALUES (?, '2020-01-01 00:00:00+00', NULL, 'snap-258', 'fixture',
                  'HOSE', 'COMMON_EQUITY', 'ACTIVE', NULL, NULL, ?, ?, NULL,
                  NULL, 'ICB', 'icb-2026')
        """,
        [symbol, sector_code, sector_code],
    )


def _seed_fundamental(conn, symbol, eps=6.0, equity=45000.0, published="2026-03-31"):
    upsert_fundamental_fact(
        conn,
        FundamentalFact(
            fact_id=f"{symbol}-2025-FY-CONSOLIDATED",
            revision_number=1,
            symbol=symbol,
            fiscal_year=2025,
            fiscal_period="FY",
            statement_scope=StatementScope.CONSOLIDATED,
            published_at=published,
            period_end_date="2025-12-31",
            audit_status=AuditStatus.AUDITED,
            currency="VND",
            unit="VND_MILLION",
            eps=eps,
            net_income=9000.0,
            total_equity=equity,
            total_liabilities=35000.0,
        ),
    )


def test_metrics_reproduce_deterministically() -> None:
    m = compute_valuation_metrics(
        ValuationInputs(price=120.0, eps=6.0, book_value_per_share=40.0)
    )
    assert m.pe_ratio == pytest.approx(20.0)
    assert m.earnings_yield == pytest.approx(6.0 / 120.0)
    assert m.pb_ratio == pytest.approx(3.0)
    assert m.book_yield == pytest.approx(40.0 / 120.0)


def test_metrics_fail_closed_on_non_positive_or_missing() -> None:
    # Zero/negative EPS or book value -> no positive multiple.
    m = compute_valuation_metrics(
        ValuationInputs(price=100.0, eps=0.0, book_value_per_share=-5.0)
    )
    assert m.pe_ratio is None
    assert m.pb_ratio is None
    # Missing price -> yields undefined.
    m2 = compute_valuation_metrics(
        ValuationInputs(price=None, eps=6.0, book_value_per_share=40.0)
    )
    assert m2.earnings_yield is None


def test_percentile_rank_is_deterministic() -> None:
    assert percentile_rank(10.0, [5.0, 10.0, 15.0]) == pytest.approx(50.0)
    assert percentile_rank(1.0, [5.0, 10.0]) == pytest.approx(0.0)
    assert percentile_rank(None, [1.0]) is None
    assert percentile_rank(1.0, []) is None


def test_build_snapshot_computes_pe_from_price_and_eps(conn) -> None:
    _seed_symbol(conn, "FPT")
    _seed_price(conn, "FPT", "2026-04-01", 120.0)
    _seed_fundamental(conn, "FPT", eps=6.0, equity=45000.0)

    snap = build_valuation_snapshot(
        conn, "FPT", "2026-04-02", shares_outstanding=1000.0
    )
    assert snap.price == 120.0
    assert snap.pe_ratio == pytest.approx(20.0)
    assert snap.book_value_per_share == pytest.approx(45.0)  # 45000/1000
    assert snap.pb_ratio == pytest.approx(120.0 / 45.0)
    assert snap.lineage["price_basis"] == "RAW_UNADJUSTED"
    assert snap.lineage["fundamental_period"] == "2025:FY:CONSOLIDATED"


def test_snapshot_no_future_publication_leakage(conn) -> None:
    _seed_symbol(conn, "FPT")
    _seed_price(conn, "FPT", "2026-02-01", 100.0)
    _seed_fundamental(conn, "FPT", published="2026-03-31")

    # As-of before the fundamental was published: no EPS -> no P/E.
    snap = build_valuation_snapshot(
        conn, "FPT", "2026-02-15", shares_outstanding=1000.0
    )
    assert snap.eps is None
    assert snap.pe_ratio is None
    assert "no_fundamental_available_by_as_of" in snap.caveats


def test_snapshot_no_future_price_leakage(conn) -> None:
    _seed_symbol(conn, "FPT")
    _seed_price(conn, "FPT", "2026-05-01", 130.0)  # future price
    _seed_fundamental(conn, "FPT")

    snap = build_valuation_snapshot(
        conn, "FPT", "2026-04-15", shares_outstanding=1000.0
    )
    assert snap.price is None
    assert "no_price_on_or_before_as_of" in snap.caveats


def test_missing_shares_flags_caveat_and_no_pb(conn) -> None:
    _seed_symbol(conn, "FPT")
    _seed_price(conn, "FPT", "2026-04-01", 120.0)
    _seed_fundamental(conn, "FPT")

    snap = build_valuation_snapshot(conn, "FPT", "2026-04-02")  # no shares
    assert snap.book_value_per_share is None
    assert snap.pb_ratio is None
    assert "share_count_not_available_by_as_of" in snap.caveats


def test_idempotent_rebuild_replaces_snapshot(conn) -> None:
    _seed_symbol(conn, "FPT")
    _seed_price(conn, "FPT", "2026-04-01", 120.0)
    _seed_fundamental(conn, "FPT")

    build_valuation_snapshot(conn, "FPT", "2026-04-02", shares_outstanding=1000.0)
    build_valuation_snapshot(conn, "FPT", "2026-04-02", shares_outstanding=1000.0)
    count = conn.execute(
        "SELECT COUNT(*) FROM valuation_snapshot WHERE symbol='FPT' AND as_of_date='2026-04-02'"
    ).fetchone()[0]
    assert count == 1


def test_sector_relative_percentile(conn) -> None:
    # Three tech peers with different P/E; the cheapest ranks lowest.
    for sym, close, eps in [
        ("AAA", 50.0, 5.0),
        ("BBB", 100.0, 5.0),
        ("CCC", 200.0, 5.0),
    ]:
        _seed_symbol(conn, sym, sector_code="TECH")
        _seed_price(conn, sym, "2026-04-01", close)
        _seed_fundamental(conn, sym, eps=eps)
        build_valuation_snapshot(conn, sym, "2026-04-02", shares_outstanding=1000.0)

    # Rebuild CCC last so peers (AAA P/E=10, BBB P/E=20) are visible.
    ccc = build_valuation_snapshot(conn, "CCC", "2026-04-03", shares_outstanding=1000.0)
    # CCC P/E = 40, higher than both peers -> top percentile.
    assert ccc.pe_ratio == pytest.approx(40.0)
    assert ccc.sector_pe_percentile == pytest.approx(100.0)


def test_historical_percentile_uses_only_prior_snapshots(conn) -> None:
    _seed_symbol(conn, "FPT")
    _seed_fundamental(conn, "FPT", eps=5.0)
    # Two historical snapshots at P/E 10 and 20, then a current at 30.
    _seed_price(conn, "FPT", "2026-04-01", 50.0)
    build_valuation_snapshot(conn, "FPT", "2026-04-01", shares_outstanding=1000.0)
    _seed_price(conn, "FPT", "2026-04-02", 100.0)
    build_valuation_snapshot(conn, "FPT", "2026-04-02", shares_outstanding=1000.0)
    _seed_price(conn, "FPT", "2026-04-03", 150.0)
    snap = build_valuation_snapshot(
        conn, "FPT", "2026-04-03", shares_outstanding=1000.0
    )
    # Current P/E=30 above both prior (10, 20) -> 100th percentile of history.
    assert snap.pe_ratio == pytest.approx(30.0)
    assert snap.historical_pe_percentile == pytest.approx(100.0)


def test_get_valuation_snapshot_roundtrip(conn) -> None:
    _seed_symbol(conn, "FPT")
    _seed_price(conn, "FPT", "2026-04-01", 120.0)
    _seed_fundamental(conn, "FPT")
    build_valuation_snapshot(conn, "FPT", "2026-04-02", shares_outstanding=1000.0)

    fetched = get_valuation_snapshot(conn, "FPT", "2026-04-02")
    assert fetched is not None
    assert fetched.pe_ratio == pytest.approx(20.0)
    assert fetched.lineage["sector_code"] == "TECH"
