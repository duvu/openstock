from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.research_intelligence.policy import LEGACY_SECTOR_STRENGTH_POLICY
from vnalpha.research_intelligence.sector import build_sector_strength
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    get_sector_strength_as_of,
    upsert_symbol,
)

TARGET_DATE = date(2024, 6, 28)
GENERATED_AT = datetime(2024, 6, 29, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class FeatureInput:
    symbol: str
    sector: str | None
    exact: bool = True


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_feature(conn: duckdb.DuckDBPyConnection, feature: FeatureInput) -> None:
    upsert_symbol(conn, feature.symbol, sector=feature.sector)
    bar_date = TARGET_DATE if feature.exact else date(2024, 6, 27)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, return_20d, return_60d,
            rs_20d_vs_vnindex, rs_60d_vs_vnindex, as_of_bar_date,
            feature_data_status, feature_generated_at, feature_profile,
            neutral_completeness, relative_strength_completeness
        ) VALUES (?, ?, 101, 100, 100, .1, .05, .02, .01, ?, ?, ?,
                  'STANDARD_120', 'COMPLETE', 'COMPLETE')
        """,
        [
            feature.symbol,
            TARGET_DATE,
            bar_date,
            "EXACT_DATE" if feature.exact else "STALE_DATE",
            GENERATED_AT,
        ],
    )


def _insert_members(
    conn: duckdb.DuckDBPyConnection, prefix: str, sector: str, count: int
) -> None:
    for number in range(count):
        _insert_feature(conn, FeatureInput(f"{prefix}{number}", sector))


def _build(conn: duckdb.DuckDBPyConnection):
    return build_sector_strength(
        conn,
        TARGET_DATE,
        generated_at=GENERATED_AT,
        policy=LEGACY_SECTOR_STRENGTH_POLICY,
    )


def test_rebuild_replaces_omitted_same_date_sectors_and_clears_no_rankable_state(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: two rankable sectors persisted for one research date.
    _insert_members(conn, "T", "Technology", 3)
    _insert_members(conn, "F", "Financials", 3)
    _build(conn)

    # When: one sector falls below threshold, then all sectors do.
    conn.execute("DELETE FROM feature_snapshot WHERE symbol = 'F0'")
    after_financial_loss = _build(conn)
    conn.execute("DELETE FROM feature_snapshot WHERE symbol LIKE 'T%'")
    result = _build(conn)

    # Then: neither obsolete sector survives either replacement.
    assert [snapshot.sector for snapshot in after_financial_loss.snapshots] == [
        "Technology"
    ]
    assert result.snapshots == ()
    assert get_sector_strength_as_of(conn, TARGET_DATE) == []
