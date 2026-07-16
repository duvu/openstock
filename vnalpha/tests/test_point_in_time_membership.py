"""Golden coverage for the point-in-time identity/classification resolver (#149).

Scenarios: listing, delisting, symbol change, sector reclassification, taxonomy
change and ambiguous overlap, plus determinism and lineage. These prove that a
recomputed historical date uses the classification effective on that date rather
than current ``symbol_master`` state.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date

import duckdb
import pytest

from vnalpha.research_intelligence.breadth import (
    _load_pit_membership as breadth_members,
)
from vnalpha.research_intelligence.sector_context import (
    _load_pit_membership as sector_members,
)
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.point_in_time import (
    RESOLVER_VERSION,
    resolve_symbol_classification,
    resolve_universe,
)


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _history(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    *,
    effective_from: str,
    effective_to: str | None,
    exchange: str = "HOSE",
    sector_name: str = "Technology",
    security_type: str = "COMMON_EQUITY",
    lifecycle_status: str = "ACTIVE",
    listing_date: date | None = None,
    delisting_date: date | None = None,
    taxonomy_name: str = "ICB",
    taxonomy_version: str = "2024",
    snapshot_id: str = "snap-1",
) -> None:
    conn.execute(
        """
        INSERT INTO symbol_classification_history (
            symbol, effective_from, effective_to, source_snapshot_id,
            classification_source, exchange, security_type, lifecycle_status,
            listing_date, delisting_date, sector_code, sector_name,
            industry_code, industry_name, taxonomy_name, taxonomy_version
        ) VALUES (?, ?, ?, ?, 'fixture', ?, ?, ?, ?, ?, ?, ?, 'IND', 'Industry',
                  ?, ?)
        """,
        [
            symbol,
            effective_from,
            effective_to,
            snapshot_id,
            exchange,
            security_type,
            lifecycle_status,
            listing_date,
            delisting_date,
            sector_name[:4].upper(),
            sector_name,
            taxonomy_name,
            taxonomy_version,
        ],
    )


def test_symbol_listed_after_date_is_excluded(conn: duckdb.DuckDBPyConnection) -> None:
    _history(
        conn,
        "NEW",
        effective_from="2024-05-01",
        effective_to=None,
        listing_date=date(2024, 5, 1),
    )
    universe = resolve_universe(conn, date(2024, 3, 15))
    assert "NEW" not in universe.symbols
    assert resolve_symbol_classification(conn, "NEW", date(2024, 3, 15)) is None
    # Eligible once the date reaches the listing date.
    assert "NEW" in resolve_universe(conn, date(2024, 6, 1)).symbols


def test_symbol_delisted_before_date_is_excluded(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _history(
        conn,
        "OLD",
        effective_from="2024-01-01",
        effective_to=None,
        listing_date=date(2024, 1, 1),
        delisting_date=date(2024, 4, 1),
    )
    # Active on a date before delisting.
    assert "OLD" in resolve_universe(conn, date(2024, 3, 15)).symbols
    # Excluded on/after the delisting date.
    assert "OLD" not in resolve_universe(conn, date(2024, 4, 1)).symbols
    assert "OLD" not in resolve_universe(conn, date(2024, 5, 1)).symbols


def test_sector_reclassification_is_point_in_time(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _history(
        conn,
        "RCL",
        effective_from="2024-01-01",
        effective_to="2024-06-01",
        sector_name="Technology",
        listing_date=date(2024, 1, 1),
    )
    _history(
        conn,
        "RCL",
        effective_from="2024-06-01",
        effective_to=None,
        sector_name="Industrials",
        listing_date=date(2024, 1, 1),
        snapshot_id="snap-2",
    )
    before = resolve_symbol_classification(conn, "RCL", date(2024, 3, 1))
    after = resolve_symbol_classification(conn, "RCL", date(2024, 7, 1))
    assert before is not None and before.sector == "Technology"
    assert after is not None and after.sector == "Industrials"


def test_taxonomy_version_change_is_point_in_time(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _history(
        conn,
        "TAX",
        effective_from="2024-01-01",
        effective_to="2024-06-01",
        taxonomy_version="2023",
        listing_date=date(2024, 1, 1),
    )
    _history(
        conn,
        "TAX",
        effective_from="2024-06-01",
        effective_to=None,
        taxonomy_version="2024",
        listing_date=date(2024, 1, 1),
        snapshot_id="snap-2",
    )
    before = resolve_symbol_classification(conn, "TAX", date(2024, 3, 1))
    after = resolve_symbol_classification(conn, "TAX", date(2024, 7, 1))
    assert before is not None and before.taxonomy_version == "2023"
    assert after is not None and after.taxonomy_version == "2024"


def test_exchange_change_resolves_point_in_time(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # A symbol change / cross-listing modeled as an exchange move.
    _history(
        conn,
        "MOV",
        effective_from="2024-01-01",
        effective_to="2024-06-01",
        exchange="HNX",
        listing_date=date(2024, 1, 1),
    )
    _history(
        conn,
        "MOV",
        effective_from="2024-06-01",
        effective_to=None,
        exchange="HOSE",
        listing_date=date(2024, 1, 1),
        snapshot_id="snap-2",
    )
    assert (
        resolve_symbol_classification(conn, "MOV", date(2024, 3, 1)).exchange == "HNX"
    )
    assert (
        resolve_symbol_classification(conn, "MOV", date(2024, 7, 1)).exchange == "HOSE"
    )


def test_ambiguous_overlap_is_flagged_but_deterministic(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Two rows with overlapping effective intervals on the requested date.
    _history(
        conn,
        "AMB",
        effective_from="2024-01-01",
        effective_to=None,
        sector_name="Technology",
        listing_date=date(2024, 1, 1),
        snapshot_id="snap-1",
    )
    _history(
        conn,
        "AMB",
        effective_from="2024-02-01",
        effective_to=None,
        sector_name="Financials",
        listing_date=date(2024, 1, 1),
        snapshot_id="snap-2",
    )
    universe = resolve_universe(conn, date(2024, 3, 1))
    assert "AMB" in universe.symbols
    assert universe.is_ambiguous("AMB")
    # Deterministic winner: latest effective_from, then highest snapshot id.
    first = resolve_symbol_classification(conn, "AMB", date(2024, 3, 1))
    second = resolve_symbol_classification(conn, "AMB", date(2024, 3, 1))
    assert first.sector == second.sector == "Financials"


def test_resolver_is_deterministic(conn: duckdb.DuckDBPyConnection) -> None:
    for sym in ("AAA", "BBB", "CCC"):
        _history(
            conn,
            sym,
            effective_from="2024-01-01",
            effective_to=None,
            listing_date=date(2024, 1, 1),
        )
    first = resolve_universe(conn, date(2024, 3, 1))
    second = resolve_universe(conn, date(2024, 3, 1))
    assert first.symbols == second.symbols
    assert first.lineage() == second.lineage()


def test_lineage_records_resolver_version_and_coverage(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _history(
        conn,
        "AAA",
        effective_from="2024-01-01",
        effective_to=None,
        listing_date=date(2024, 1, 1),
    )
    _history(
        conn,
        "LATE",
        effective_from="2024-05-01",
        effective_to=None,
        listing_date=date(2024, 5, 1),
    )
    universe = resolve_universe(conn, date(2024, 3, 1))
    lineage = universe.lineage()
    assert lineage["pit_resolver_version"] == RESOLVER_VERSION
    assert lineage["pit_as_of_date"] == "2024-03-01"
    assert lineage["pit_eligible_symbol_count"] == "1"  # only AAA
    assert lineage["pit_known_symbol_count"] == "2"
    assert float(lineage["pit_coverage"]) == pytest.approx(0.5)


def test_breadth_membership_uses_point_in_time_history(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _history(
        conn,
        "AAA",
        effective_from="2024-01-01",
        effective_to=None,
        exchange="HOSE",
        listing_date=date(2024, 1, 1),
    )
    _history(
        conn,
        "LATE",
        effective_from="2024-05-01",
        effective_to=None,
        exchange="HNX",
        listing_date=date(2024, 5, 1),
    )
    rows, basis, resolver_version = breadth_members(conn, date(2024, 3, 1))
    symbols = {row[0] for row in rows}
    assert symbols == {"AAA"}  # LATE not yet listed
    assert rows[0] == ("AAA", "HOSE", "COMMON_EQUITY")
    assert basis == "symbol_classification_history"
    assert resolver_version is not None


def test_sector_membership_uses_point_in_time_history(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _history(
        conn,
        "AAA",
        effective_from="2024-01-01",
        effective_to="2024-06-01",
        sector_name="Technology",
        listing_date=date(2024, 1, 1),
    )
    _history(
        conn,
        "AAA",
        effective_from="2024-06-01",
        effective_to=None,
        sector_name="Industrials",
        listing_date=date(2024, 1, 1),
        snapshot_id="snap-2",
    )
    early = {row[0]: row[1] for row in sector_members(conn, date(2024, 3, 1))[0]}
    late = {row[0]: row[1] for row in sector_members(conn, date(2024, 7, 1))[0]}
    assert early["AAA"] == "Technology"
    assert late["AAA"] == "Industrials"


def test_no_history_falls_back_to_current_symbol_master(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # No classification history rows; current-only warehouse must still work.
    conn.execute(
        "INSERT INTO symbol_master (symbol, exchange, sector, security_type, "
        "is_active, lifecycle_status, last_seen_at) "
        "VALUES ('CUR', 'HOSE', 'Technology', 'COMMON_EQUITY', TRUE, 'ACTIVE', "
        "current_timestamp)"
    )
    rows, basis, resolver_version = breadth_members(conn, date(2024, 3, 1))
    assert ("CUR", "HOSE", "COMMON_EQUITY") in rows
    assert basis == "symbol_master"
    assert resolver_version is None
    sector_rows = {row[0]: row[1] for row in sector_members(conn, date(2024, 3, 1))[0]}
    assert sector_rows["CUR"] == "Technology"
