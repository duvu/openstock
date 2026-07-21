from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    get_sector_strength_as_of,
    upsert_symbol,
)

TARGET_DATE = date(2024, 6, 28)
GENERATED_AT = datetime(2024, 6, 29, tzinfo=timezone.utc)
GOLDEN_FIXTURE = Path(__file__).parent / "fixtures" / "sector_context_golden.json"
PROHIBITED_TERMS = (
    "allocation",
    "portfolio",
    "buy",
    "sell",
    "order",
    "broker",
    "margin",
    "trade",
    "trading",
    "execution",
    "recommendation",
)


@dataclass(frozen=True, slots=True)
class FeatureFixture:
    symbol: str
    sector: str | None
    return20: float = 0.10
    return60: float = 0.05
    rs20: float = 0.02
    rs60: float = 0.01
    above_ma20: bool = True
    above_ma50: bool = True
    exact: bool = True


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_feature(conn: duckdb.DuckDBPyConnection, fixture: FeatureFixture) -> None:
    upsert_symbol(conn, fixture.symbol, sector=fixture.sector)
    close = 101.0 if fixture.above_ma20 else 99.0
    ma50 = 100.0 if fixture.above_ma50 else 102.0
    as_of_bar_date = TARGET_DATE if fixture.exact else date(2024, 6, 27)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, return_20d, return_60d,
            rs_20d_vs_vnindex, rs_60d_vs_vnindex, as_of_bar_date,
            feature_data_status, source_row_count, feature_build_version,
            feature_generated_at, lineage_json, feature_profile,
            neutral_completeness, relative_strength_completeness,
            required_bar_count, observed_bar_count,
            feature_completeness_rule_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            fixture.symbol,
            TARGET_DATE,
            close,
            100.0,
            ma50,
            fixture.return20,
            fixture.return60,
            fixture.rs20,
            fixture.rs60,
            as_of_bar_date,
            "EXACT_DATE" if fixture.exact else "STALE_DATE",
            120,
            "fixture-v1",
            GENERATED_AT,
            '{"fixture":"sector"}',
            "STANDARD_120",
            "COMPLETE" if fixture.exact else "INCOMPLETE",
            "COMPLETE",
            120,
            120,
            "feature-completeness-v1",
        ],
    )


def _build(conn: duckdb.DuckDBPyConnection):
    from vnalpha.research_intelligence.policy import LEGACY_SECTOR_STRENGTH_POLICY
    from vnalpha.research_intelligence.sector import build_sector_strength

    return build_sector_strength(
        conn,
        TARGET_DATE,
        generated_at=GENERATED_AT,
        policy=LEGACY_SECTOR_STRENGTH_POLICY,
    )


def test_build_sector_strength_ranks_tied_scores_alphabetically_and_persists(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: two eligible sectors with identical aggregate measurements.
    for sector in ("Beta", "Alpha"):
        for number in range(3):
            _insert_feature(conn, FeatureFixture(f"{sector[:1]}{number}", sector))

    # When: the same dated context is built twice with a fixed timestamp.
    first = _build(conn)
    second = _build(conn)

    # Then: alphabetic ordering breaks the score and RS tie deterministically.
    assert first == second
    assert [snapshot.sector for snapshot in first.snapshots] == ["Alpha", "Beta"]
    assert [snapshot.rank for snapshot in first.snapshots] == [1, 2]
    assert get_sector_strength_as_of(conn, TARGET_DATE) == list(first.snapshots)
