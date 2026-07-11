from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)
from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.models import ToolPermission
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    upsert_market_regime_snapshot,
    upsert_sector_strength_snapshots,
    upsert_symbol,
)


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


def test_market_context_returns_latest_persisted_snapshot_with_disclosures(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    upsert_market_regime_snapshot(conn, _regime_snapshot(date(2026, 7, 1)))
    upsert_market_regime_snapshot(conn, _regime_snapshot(date(2026, 7, 2)))

    output = build_local_tool_registry(conn).call(
        "market.get_regime", {ToolPermission.READ_FEATURES}
    )

    assert output.data["lookup"] == "latest"
    assert output.data["as_of_date"] == "2026-07-02"
    assert output.data["methodology_version"] == "market-regime-v1"
    assert output.data["freshness"]["benchmark_bar_date"] == "2026-07-02"
    assert output.data["lineage"]["benchmark_freshness"] == "EXACT_DATE"
    assert output.data["quality"] == "COMPLETE"
    assert output.data["caveats"] == ["Breadth excludes nonexact rows."]


def test_market_context_returns_exact_requested_date_and_truthful_missing_output(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    upsert_market_regime_snapshot(conn, _regime_snapshot(date(2026, 7, 2)))
    registry = build_local_tool_registry(conn)

    exact = registry.call(
        "market.get_regime", {ToolPermission.READ_FEATURES}, date="2026-07-02"
    )
    missing = registry.call(
        "market.get_regime", {ToolPermission.READ_FEATURES}, date="2026-07-01"
    )

    assert exact.data["lookup"] == "exact"
    assert exact.data["requested_date"] == "2026-07-02"
    assert exact.data["as_of_date"] == "2026-07-02"
    assert missing.data["snapshot"] is None
    assert missing.data["as_of_date"] is None
    assert missing.data["requested_date"] == "2026-07-01"
    assert missing.data["quality"] == "INSUFFICIENT_DATA"
    assert missing.data["as_of_date"] is None
    assert missing.data["caveats"]


def test_sector_context_preserves_rank_order_and_rejects_nonpositive_top(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    as_of_date = date(2026, 7, 2)
    upsert_sector_strength_snapshots(
        conn,
        (
            _sector_snapshot(as_of_date, "Industrials", 2),
            _sector_snapshot(as_of_date, "Technology", 1),
            _sector_snapshot(as_of_date, "Financials", 1),
        ),
    )
    registry = build_local_tool_registry(conn)

    output = registry.call("sector.get_strength", {ToolPermission.READ_FEATURES}, top=2)

    assert output.data["lookup"] == "latest"
    assert [item["sector"] for item in output.data["snapshots"]] == [
        "Financials",
        "Technology",
    ]
    assert output.data["methodology_version"] == "sector-strength-v1"
    assert output.data["freshness"]["generated_at"]
    assert output.data["quality"] == "COMPLETE"
    with pytest.raises(ToolExecutionError, match="positive integer"):
        registry.call("sector.get_strength", {ToolPermission.READ_FEATURES}, top=0)


def test_sector_context_exact_missing_and_alignment_missing_states_are_truthful(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    as_of_date = date(2026, 7, 2)
    snapshot = _sector_snapshot(as_of_date, "Technology", 1)
    upsert_sector_strength_snapshots(conn, (snapshot,))
    upsert_symbol(conn, "FPT", sector="Technology")
    upsert_symbol(conn, "VNM")
    registry = build_local_tool_registry(conn)

    missing = registry.call(
        "sector.get_strength",
        {ToolPermission.READ_FEATURES},
        date="2026-07-01",
    )
    aligned = registry.call(
        "sector.get_symbol_alignment",
        {ToolPermission.READ_FEATURES},
        symbol=" fpt ",
    )
    no_metadata = registry.call(
        "sector.get_symbol_alignment",
        {ToolPermission.READ_FEATURES},
        symbol="VNM",
    )
    no_snapshot = registry.call(
        "sector.get_symbol_alignment",
        {ToolPermission.READ_FEATURES},
        symbol="FPT",
        date="2026-07-01",
    )

    assert missing.data["lookup"] == "exact"
    assert missing.data["quality"] == "INSUFFICIENT_DATA"
    assert aligned.data["symbol"] == "FPT"
    assert aligned.data["snapshot"]["sector"] == "Technology"
    assert no_metadata.data["sector"] is None
    assert no_metadata.data["as_of_date"] is None
    assert no_metadata.data["quality"] == "INSUFFICIENT_DATA"
    assert no_snapshot.data["sector"] == "Technology"
    assert no_snapshot.data["snapshot"] is None
    assert no_snapshot.data["as_of_date"] is None
    assert no_snapshot.data["caveats"]


@pytest.mark.parametrize("top", [True, 1.0, "1.5", "-1.5", 0, -1])
def test_sector_context_rejects_non_integer_or_nonpositive_top(
    conn: duckdb.DuckDBPyConnection, top: int | float | str | bool
) -> None:
    with pytest.raises(ToolExecutionError, match="positive integer"):
        build_local_tool_registry(conn).call(
            "sector.get_strength", {ToolPermission.READ_FEATURES}, top=top
        )
