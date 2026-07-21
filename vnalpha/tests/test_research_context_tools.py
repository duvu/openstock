from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)
from vnalpha.tools.models import ToolPermission
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.migrations import run_migrations


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
        quality="COMPLETE",
        caveats=("Breadth excludes nonexact rows.",),
        lineage={"benchmark_freshness": "EXACT_DATE"},
        methodology_version="market-regime-v1",
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
        quality="COMPLETE",
        caveats=("One eligible symbol lacks sector metadata.",),
        lineage={"feature_data_freshness": "EXACT_DATE"},
        methodology_version="sector-strength-v1",
        generated_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def test_context_tools_register_as_autonomous_read_only_feature_reads(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    registry = build_local_tool_registry(conn)

    for name in (
        "market.get_regime",
        "sector.get_strength",
        "sector.get_symbol_alignment",
    ):
        assert registry.get_spec(name).permission is ToolPermission.READ_FEATURES

    from vnalpha.policy.assistant_policy import AUTONOMOUS_PLAN_TOOL_NAMES
    from vnalpha.policy.tool_policy import TOOL_CAPABILITIES_BY_NAME

    for name in (
        "market.get_regime",
        "sector.get_strength",
        "sector.get_symbol_alignment",
    ):
        capability = TOOL_CAPABILITIES_BY_NAME[name]
        assert capability.allowed_for_assistant
        assert capability.allowed_for_command
        assert capability.allowed_for_autonomous_plan
        assert not capability.mutates_warehouse
        assert name in AUTONOMOUS_PLAN_TOOL_NAMES
