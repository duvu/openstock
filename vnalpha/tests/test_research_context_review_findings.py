from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.commands.executor import CommandExecutor
from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    upsert_symbol,
)


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _execute(conn: duckdb.DuckDBPyConnection, command: str):
    return CommandExecutor(conn, surface="test").execute(command)


def _market_snapshot(caveats: tuple[str, ...] = ()) -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        as_of_date=date(2026, 7, 2),
        benchmark_symbol="VNINDEX",
        benchmark_bar_date=date(2026, 7, 1),
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
        quality="COMPLETE",
        caveats=caveats,
        lineage={"freshness_basis": "benchmark_bar_date", "source": "canonical"},
        methodology_version="v1",
        generated_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )


def _sector_snapshot(
    *,
    rank: int = 1,
    score: float = 0.82,
    rotation: str = "STABLE",
    quality: str = "COMPLETE",
    caveats: tuple[str, ...] = (),
) -> SectorStrengthSnapshot:
    return SectorStrengthSnapshot(
        as_of_date=date(2026, 7, 2),
        sector="Technology",
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
        score=score,
        rotation=rotation,
        metadata_coverage=0.90,
        unclassified_count=1,
        quality=quality,
        caveats=caveats,
        lineage={
            "freshness_basis": "as_of_date",
            "source": "feature_snapshot",
            "pipeline": "eod",
        },
        methodology_version="v1",
        generated_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )


def _alignment_value(result) -> str:
    for panel in result.panels:
        if panel.title == "Sector Alignment":
            return panel.content["Alignment"]
    raise AssertionError("Sector Alignment panel missing")


def test_symbol_alignment_discloses_unclassified_and_missing_snapshot_context(
    conn,
) -> None:
    upsert_symbol(conn, "VNM")
    upsert_symbol(conn, "HPG", sector="Materials")

    unclassified = _execute(conn, "/sector-strength VNM")
    missing_snapshot = _execute(conn, "/sector-strength HPG")

    assert _alignment_value(unclassified) == "INSUFFICIENT_DATA"
    assert _alignment_value(missing_snapshot) == "INSUFFICIENT_DATA"
