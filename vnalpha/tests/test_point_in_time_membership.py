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

from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.point_in_time import (
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
