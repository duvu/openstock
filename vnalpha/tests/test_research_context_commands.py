from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.models import CommandStatus
from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    upsert_market_regime_snapshot,
)


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _regime_snapshot(as_of_date: date) -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        as_of_date=as_of_date,
        benchmark_symbol="VNINDEX",
        benchmark_bar_date=as_of_date,
        close=1300.0,
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
        quality="PARTIAL",
        caveats=("Coverage excludes inactive symbols.",),
        lineage={"freshness_basis": "benchmark_bar_date", "source": "canonical"},
        methodology_version="v1",
        generated_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
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
        quality="PARTIAL",
        caveats=(f"{sector} coverage is partial.",),
        lineage={"freshness_basis": "as_of_date", "source": "feature_snapshot"},
        methodology_version="v1",
        generated_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )


def _execute(conn: duckdb.DuckDBPyConnection, command: str):
    return CommandExecutor(conn, surface="test").execute(command)


def test_market_regime_reads_latest_and_exact_persisted_context(conn) -> None:
    older = _regime_snapshot(date(2026, 7, 1))
    latest = _regime_snapshot(date(2026, 7, 2))
    upsert_market_regime_snapshot(conn, older)
    upsert_market_regime_snapshot(conn, latest)

    latest_result = _execute(conn, "/market-regime")
    exact_result = _execute(conn, "/market-regime --date 2026-07-01")

    assert latest_result.status is CommandStatus.PARTIAL
    assert latest_result.panels
    assert any("Regime" in panel.title for panel in latest_result.panels)
    assert any("Breadth" in panel.title for panel in latest_result.panels)
    assert "2026-07-02" in str(latest_result.panels)
    assert latest.caveats[0] in latest_result.warnings
    assert exact_result.status is CommandStatus.PARTIAL
    assert "2026-07-01" in str(exact_result.panels)
