from __future__ import annotations

import duckdb

from vnalpha.disclosures import DisclosureOccurrence, EventType, as_of_events, normalize_event
from vnalpha.fundamentals import (
    AuditStatus,
    FundamentalFact,
    StatementScope,
    as_of_snapshot,
    upsert_fundamental_fact,
)
from vnalpha.valuation import (
    ShareCountFact,
    build_valuation_snapshot,
    upsert_share_count_fact,
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


def _price(conn: duckdb.DuckDBPyConnection, symbol: str, day: str, close: float) -> None:
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


def test_later_disclosure_revision_does_not_erase_historical_view() -> None:
    conn = _conn()
    first = DisclosureOccurrence(
        source_authority="HSX",
        source_reference="hsx://event-1/v1",
        symbol="FPT",
        published_at="2026-07-01",
        raw_title="Board resolution v1",
        raw_payload={"version": 1},
    )
    second = DisclosureOccurrence(
        source_authority="HSX",
        source_reference="hsx://event-1/v2",
        symbol="FPT",
        published_at="2026-07-10",
        raw_title="Board resolution v2",
        raw_payload={"version": 2},
    )
    first_event = normalize_event(
        conn,
        first,
        event_type=EventType.SHAREHOLDER_MEETING,
        event_id="event-1",
        event_date="2026-07-20",
    )
    normalize_event(
        conn,
        second,
        event_type=EventType.SHAREHOLDER_MEETING,
        event_id="event-1",
        event_date="2026-07-21",
    )

    historical = as_of_events(conn, "FPT", "2026-07-05")
    current = as_of_events(conn, "FPT", "2026-07-15")
    assert historical[0]["revision_id"] == first_event.revision_id
    assert historical[0]["published_at"] == "2026-07-01"
    assert current[0]["revision_number"] == 2
    conn.close()


def test_valuation_uses_point_in_time_sector_and_verified_share_fact() -> None:
    conn = _conn()
    _classification(conn, "FPT", "TECH", "2026-01-01", "2026-07-10", "fpt-tech")
    _classification(conn, "FPT", "FIN", "2026-07-10", None, "fpt-fin")
    _classification(conn, "AAA", "TECH", "2026-01-01", None, "aaa-tech")
    _classification(conn, "BBB", "FIN", "2026-01-01", None, "bbb-fin")
    _price(conn, "FPT", "2026-07-05", 100.0)
    upsert_fundamental_fact(
        conn,
        _fact(available_from="2026-07-01T09:00:00+07:00"),
    )
    share_revision = upsert_share_count_fact(
        conn,
        ShareCountFact(
            fact_id="FPT-shares",
            revision_number=1,
            symbol="FPT",
            effective_date="2026-01-01",
            available_from="2026-01-02T09:00:00+07:00",
            shares_outstanding=100.0,
            source_reference="hsx://fpt/shares/1",
            source_authority="HSX",
        ),
    )
    conn.executemany(
        """
        INSERT INTO valuation_snapshot (
            snapshot_id, symbol, as_of_date, price, price_basis, pe_ratio,
            caveats_json, lineage_json, contract_version
        ) VALUES (?, ?, '2026-07-04', 100, 'RAW_UNADJUSTED', ?, '[]', '{}', 'fixture')
        """,
        [("peer-tech", "AAA", 5.0), ("peer-fin", "BBB", 30.0)],
    )

    snapshot = build_valuation_snapshot(conn, "FPT", "2026-07-05")
    assert snapshot.lineage["sector_code"] == "TECH"
    assert snapshot.lineage["classification_source_snapshot_id"] == "fpt-tech"
    assert snapshot.lineage["share_count_revision_id"] == share_revision
    assert snapshot.lineage["share_count_evidence_status"] == "VERIFIED_FACT"
    assert snapshot.lineage["sector_peer_count"] == 1
    assert snapshot.sector_pe_percentile is not None
    conn.close()


def test_valuation_rebuild_preserves_immutable_revision_history() -> None:
    conn = _conn()
    _classification(conn, "FPT", "TECH", "2026-01-01", None, "fpt-tech")
    _price(conn, "FPT", "2026-07-05", 100.0)
    upsert_fundamental_fact(
        conn,
        _fact(available_from="2026-07-01T09:00:00+07:00"),
    )
    upsert_share_count_fact(
        conn,
        ShareCountFact(
            fact_id="FPT-shares",
            revision_number=1,
            symbol="FPT",
            effective_date="2026-01-01",
            available_from="2026-01-02T09:00:00+07:00",
            shares_outstanding=100.0,
            source_reference="hsx://fpt/shares/1",
            source_authority="HSX",
        ),
    )
    first = build_valuation_snapshot(conn, "FPT", "2026-07-05")
    upsert_share_count_fact(
        conn,
        ShareCountFact(
            fact_id="FPT-shares",
            revision_number=2,
            symbol="FPT",
            effective_date="2026-01-01",
            available_from="2026-07-04T09:00:00+07:00",
            shares_outstanding=200.0,
            source_reference="hsx://fpt/shares/2",
            source_authority="HSX",
        ),
    )
    second = build_valuation_snapshot(conn, "FPT", "2026-07-05")
    assert first.snapshot_id != second.snapshot_id
    revisions = conn.execute(
        """
        SELECT revision_number, canonical_status
        FROM valuation_snapshot_revision
        ORDER BY revision_number
        """
    ).fetchall()
    assert revisions == [(1, "SUPERSEDED"), (2, "CURRENT")]
    conn.close()
