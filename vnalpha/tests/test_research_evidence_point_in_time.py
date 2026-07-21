from __future__ import annotations

import duckdb

from vnalpha.fundamentals import (
    AuditStatus,
    FundamentalFact,
    StatementScope,
    as_of_snapshot,
    upsert_fundamental_fact,
)
from vnalpha.warehouse.migrations import run_migrations


def _conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    return conn


def _fact(
    *,
    revision: int = 1,
    available_from: str = "2026-07-03T09:00:00+07:00",
    eps: float = 10.0,
    equity: float = 1_000.0,
) -> FundamentalFact:
    return FundamentalFact(
        fact_id="FPT-2026-Q2",
        revision_number=revision,
        symbol="FPT",
        fiscal_year=2026,
        fiscal_period="Q2",
        statement_scope=StatementScope.CONSOLIDATED,
        published_at="2026-07-01",
        available_from=available_from,
        period_end_date="2026-06-30",
        audit_status=AuditStatus.REVIEWED,
        currency="VND",
        unit="million_vnd",
        revenue=2_000.0,
        net_income=100.0,
        eps=eps,
        total_assets=3_000.0,
        total_equity=equity,
        total_liabilities=2_000.0,
        operating_cash_flow=120.0,
        source_reference=f"issuer://FPT/q2/rev-{revision}",
        source_authority="ISSUER",
    )


def _classification(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    sector: str,
    start: str,
    end: str | None,
    snapshot_id: str,
) -> None:
    conn.execute(
        """
        INSERT INTO symbol_classification_history (
            symbol, effective_from, effective_to, source_snapshot_id,
            classification_source, exchange, security_type, lifecycle_status,
            listing_date, sector_code, sector_name, taxonomy_name,
            taxonomy_version
        ) VALUES (?, ?, ?, ?, 'VCI', 'HOSE', 'STOCK', 'ACTIVE',
                  '2020-01-01', ?, ?, 'ICB', 'v1')
        """,
        [symbol, start, end, snapshot_id, sector, sector],
    )


def _price(
    conn: duckdb.DuckDBPyConnection, symbol: str, day: str, close: float
) -> None:
    conn.execute(
        """
        INSERT INTO canonical_ohlcv (
            symbol, time, interval, close, selected_provider, price_basis,
            quality_status, ingestion_run_id
        ) VALUES (?, ?, '1D', ?, 'VCI', 'RAW_UNADJUSTED', 'PASS', ?)
        """,
        [symbol, day, close, f"run-{symbol}-{day}"],
    )


def test_fundamental_visibility_uses_available_from_not_publication_label() -> None:
    conn = _conn()
    upsert_fundamental_fact(conn, _fact())
    assert as_of_snapshot(conn, "FPT", "2026-07-02") == []
    visible = as_of_snapshot(conn, "FPT", "2026-07-03")
    assert len(visible) == 1
    assert visible[0].available_from.startswith("2026-07-03")
    assert visible[0].revision_id
    conn.close()
