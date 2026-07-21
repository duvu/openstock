from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from vnalpha.data_availability.deep_context_evidence import market_issues, sector_issues
from vnalpha.data_availability.deep_readiness_models import ContextIssue
from vnalpha.research_intelligence.regime import build_market_regime
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import upsert_symbol

TARGET_DATE = date(2024, 6, 28)
GENERATED_AT = datetime(2024, 6, 29, tzinfo=timezone.utc)
GOLDEN = json.loads(
    (
        Path(__file__).parent / "fixtures" / "market_context_production_golden.json"
    ).read_text()
)


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_benchmark(conn: duckdb.DuckDBPyConnection, closes: list[float]) -> None:
    dates = pd.date_range(end=TARGET_DATE, periods=len(closes), freq="B")
    rows = [
        (
            "VNINDEX",
            timestamp.date(),
            "1D",
            close,
            close,
            close,
            close,
            1_000_000.0,
            "fixture",
            "PASS",
            "benchmark-run",
            "service-run",
        )
        for timestamp, close in zip(dates, closes, strict=True)
    ]
    conn.executemany(
        """
        INSERT INTO canonical_ohlcv (
            symbol, time, interval, open, high, low, close, volume,
            selected_provider, quality_status, ingestion_run_id, source_service_run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _insert_symbol_feature(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    *,
    sector: str | None = "Technology",
    exchange: str = "HOSE",
    security_type: str = "COMMON_EQUITY",
    return20: float = 0.10,
    return60: float = 0.05,
    rs20: float = 0.03,
    rs60: float = 0.01,
    above_ma20: bool = True,
    above_ma50: bool = True,
    volume_ma20: float = 20_000.0,
    taxonomy: bool = True,
) -> None:
    upsert_symbol(conn, symbol, exchange=exchange, sector=sector)
    conn.execute(
        """
        UPDATE symbol_master
        SET security_type = ?, lifecycle_status = 'ACTIVE', sector_name = ?,
            taxonomy_name = ?, taxonomy_version = ?
        WHERE symbol = ?
        """,
        [
            security_type,
            sector,
            "ICB" if taxonomy and sector else None,
            "2024" if taxonomy and sector else None,
            symbol,
        ],
    )
    close = 101.0 if above_ma20 else 99.0
    ma50 = 100.0 if above_ma50 else 102.0
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, volume_ma20,
            return_20d, return_60d, rs_20d_vs_vnindex, rs_60d_vs_vnindex,
            distance_to_52w_high, as_of_bar_date, feature_data_status,
            source_row_count, feature_build_version, feature_generated_at,
            lineage_json, feature_profile, neutral_completeness,
            relative_strength_completeness, required_bar_count,
            observed_bar_count, feature_completeness_rule_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'EXACT_DATE', 120,
                  'fixture-v2', ?, '{"fixture":"production-context"}',
                  'STANDARD_120', 'COMPLETE', 'COMPLETE', 120, 120,
                  'feature-completeness-v1')
        """,
        [
            symbol,
            TARGET_DATE,
            close,
            100.0,
            ma50,
            volume_ma20,
            return20,
            return60,
            rs20,
            rs60,
            -0.002,
            TARGET_DATE,
            GENERATED_AT,
        ],
    )


def _insert_market_universe(
    conn: duckdb.DuckDBPyConnection,
    *,
    count: int,
    positive_count: int,
    above_ma20_count: int,
    above_ma50_count: int,
) -> None:
    for number in range(count):
        _insert_symbol_feature(
            conn,
            f"SYM{number:02d}",
            sector="Market",
            exchange="HOSE" if number % 2 == 0 else "HNX",
            return20=0.02 if number < positive_count else -0.02,
            above_ma20=number < above_ma20_count,
            above_ma50=number < above_ma50_count,
        )


def test_production_market_rejects_five_rows_and_records_policy(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_market_universe(
        conn,
        count=5,
        positive_count=5,
        above_ma20_count=5,
        above_ma50_count=5,
    )

    first = build_market_regime(conn, TARGET_DATE, generated_at=GENERATED_AT)
    second = build_market_regime(conn, TARGET_DATE, generated_at=GENERATED_AT)

    expected = GOLDEN["market"]["insufficient_five_rows"]
    assert first == second
    assert first.regime == expected["regime"]
    assert first.quality == expected["quality"]
    assert first.methodology_version == "market-regime-v2"
    assert first.lineage["policy_minimum_eligible_symbols"] == str(
        expected["minimum_eligible_symbols"]
    )
    assert first.breadth_eligible_count == 5
    assert market_issues(first, first, TARGET_DATE, False) == (
        ContextIssue.MARKET_REGIME_INPUT_COVERAGE_INSUFFICIENT,
    )


# ---------------------------------------------------------------------------
# #151 — metadata/taxonomy coverage thresholds govern readiness directly.
# ---------------------------------------------------------------------------

from vnalpha.research_intelligence.models import SectorStrengthSnapshot  # noqa: E402
from vnalpha.research_intelligence.policy import (  # noqa: E402
    PRODUCTION_SECTOR_STRENGTH_POLICY,
)
from vnalpha.research_intelligence.sector import (  # noqa: E402
    METHODOLOGY_VERSION as SECTOR_METHODOLOGY_VERSION,
)

_POLICY = PRODUCTION_SECTOR_STRENGTH_POLICY


def _readiness_snapshot(
    *,
    metadata_coverage: float,
    unclassified_count: int,
    taxonomy_coverage: float,
    liquidity_coverage: float = 0.90,
) -> SectorStrengthSnapshot:
    """A rankable snapshot whose only readiness variables are the coverages.

    Every per-snapshot policy gate (members, eligibility, sector coverage,
    liquidity, quality, methodology) is satisfied, so ``sector_issues`` is
    driven solely by the metadata/taxonomy coverage values under test.
    """
    lineage = {
        "taxonomy_coverage": f"{taxonomy_coverage}",
        "liquidity_coverage": f"{liquidity_coverage}",
        "sector_coverage": "0.90",
        "sector_liquidity_coverage": "0.90",
    }
    return SectorStrengthSnapshot(
        as_of_date=TARGET_DATE,
        sector="Technology",
        rank=1,
        member_count=_POLICY.minimum_sector_members,
        eligible_count=_POLICY.minimum_eligible_members,
        median_return20=0.02,
        median_return60=0.03,
        median_rs20_vs_vnindex=0.01,
        median_rs60_vs_vnindex=0.01,
        pct_above_ma20=0.60,
        pct_above_ma50=0.55,
        leadership_count=1,
        score=0.5,
        rotation="STABLE",
        metadata_coverage=metadata_coverage,
        unclassified_count=unclassified_count,
        quality="OK",
        caveats=(),
        lineage=lineage,
        methodology_version=SECTOR_METHODOLOGY_VERSION,
        generated_at=GENERATED_AT,
    )


def _issues_for(snapshot: SectorStrengthSnapshot) -> tuple[ContextIssue, ...]:
    return sector_issues([snapshot], [snapshot], TARGET_DATE, False)
