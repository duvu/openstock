from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _regime_snapshot(
    as_of_date: date, *, close: float = 1300.0
) -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        as_of_date=as_of_date,
        benchmark_symbol="VNINDEX",
        benchmark_bar_date=as_of_date,
        close=close,
        ma20=1280.0,
        ma50=1250.0,
        ma50_slope=0.02,
        return20=0.04,
        return60=0.12,
        volatility20=0.18,
        breadth_active_count=100,
        breadth_eligible_count=95,
        breadth_excluded_count=5,
        breadth_coverage=0.95,
        pct_above_ma20=0.62,
        pct_above_ma50=0.58,
        pct_positive_return20=0.55,
        regime="RISK_ON",
        trend="UPTREND",
        volatility="NORMAL",
        quality="COMPLETE",
        caveats=("Coverage excludes inactive symbols.",),
        lineage={"source": "canonical_ohlcv"},
        methodology_version="v1",
        generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _sector_snapshot(
    as_of_date: date, sector: str, rank: int
) -> SectorStrengthSnapshot:
    return SectorStrengthSnapshot(
        as_of_date=as_of_date,
        sector=sector,
        rank=rank,
        member_count=10,
        eligible_count=9,
        median_return20=0.04,
        median_return60=0.10,
        median_rs20_vs_vnindex=0.01,
        median_rs60_vs_vnindex=0.03,
        pct_above_ma20=0.66,
        pct_above_ma50=0.55,
        leadership_count=7,
        score=0.82,
        rotation="IMPROVING",
        metadata_coverage=0.90,
        unclassified_count=1,
        quality="COMPLETE",
        caveats=(),
        lineage={"source": "feature_snapshot"},
        methodology_version="v1",
        generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def test_migrations_create_market_regime_and_sector_strength_tables(conn) -> None:
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}

    assert {"market_regime_snapshot", "sector_strength_snapshot"} <= tables
