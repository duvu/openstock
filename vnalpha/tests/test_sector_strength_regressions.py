from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.research_intelligence.sector import build_sector_strength
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    get_sector_strength_as_of,
    get_symbol_sector_alignment,
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
    return build_sector_strength(conn, TARGET_DATE, generated_at=GENERATED_AT)


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


def test_feature_gaps_make_active_universe_incompleteness_visible(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a sector with exact, missing, stale, and unusable active members.
    _insert_members(conn, "E", "Energy", 3)
    upsert_symbol(conn, "MISSING", sector="Energy")
    _insert_feature(conn, FeatureInput("STALE", "Energy", exact=False))
    _insert_feature(conn, FeatureInput("UNUSABLE", "Energy"))
    conn.execute(
        "UPDATE feature_snapshot SET return_60d = NULL WHERE symbol = 'UNUSABLE'"
    )

    # When: the sector context is built.
    snapshot = _build(conn).snapshots[0]

    # Then: active feature exclusions are counted and prevent an OK quality state.
    assert snapshot.member_count == 6
    assert snapshot.eligible_count == 3
    assert snapshot.quality == "INCOMPLETE"
    assert "3 active symbols lack usable exact-date features." in snapshot.caveats
    assert snapshot.lineage["active_symbol_count"] == "6"
    assert snapshot.lineage["eligible_symbol_count"] == "3"
    assert snapshot.lineage["excluded_symbol_count"] == "3"


def test_sector_strength_rejects_incomplete_relative_strength_evidence(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a rankable sector with one row marked RS-incomplete.
    _insert_members(conn, "T", "Technology", 3)
    conn.execute(
        "UPDATE feature_snapshot SET relative_strength_completeness = 'INCOMPLETE' "
        "WHERE symbol = 'T0'"
    )

    # When: sector strength loads its profile-enforcing input context.
    result = _build(conn)

    # Then: the remaining two rows cannot form a rankable sector.
    assert result.snapshots == ()


def test_persisted_lineage_declares_exact_feature_freshness_basis(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a rankable exact-date sector.
    _insert_members(conn, "T", "Technology", 3)

    # When: the snapshot is built and read back from persistence.
    _build(conn)
    persisted = get_sector_strength_as_of(conn, TARGET_DATE)[0]

    # Then: command and tool consumers can directly inspect its freshness contract.
    assert persisted.lineage["feature_data_freshness"] == "EXACT_DATE"
    assert persisted.lineage["feature_bar_date_basis"] == "as_of_bar_date == as_of_date"


def test_member_count_keeps_classified_active_members_separate_from_eligible_rows(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: four classified active members with only three usable feature rows.
    _insert_members(conn, "T", "Technology", 3)
    upsert_symbol(conn, "NO_FEATURE", sector="Technology")

    # When: the rankable sector is built.
    snapshot = _build(conn).snapshots[0]

    # Then: membership and exact-date eligibility retain their distinct meanings.
    assert snapshot.member_count == 4
    assert snapshot.eligible_count == 3


def test_symbol_alignment_treats_whitespace_sector_as_unclassified(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: active metadata containing only whitespace for a symbol's sector.
    upsert_symbol(conn, "BLANK", sector="   ")

    # When: alignment is requested.
    alignment = get_symbol_sector_alignment(conn, "BLANK", TARGET_DATE)

    # Then: no fabricated sector or snapshot is returned.
    assert alignment is not None
    assert alignment.sector is None
    assert alignment.snapshot is None
