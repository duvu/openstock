from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.models import CommandStatus
from vnalpha.commands.setup import build_default_registry
from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    upsert_market_regime_snapshot,
    upsert_sector_strength_snapshots,
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


@pytest.mark.parametrize(
    "command",
    [
        "/market-regime FPT",
        "/market-regime --top 2",
        "/sector-strength score>0",
        "/sector-strength --unknown value",
    ],
)
def test_research_context_commands_reject_unsupported_syntax(
    conn, command: str
) -> None:
    result = _execute(conn, command)

    assert result.status is CommandStatus.VALIDATION_ERROR
    assert result.error is not None
    assert result.error.error_type == "CommandValidationError"


def _alignment_value(result) -> str:
    for panel in result.panels:
        if panel.title == "Sector Alignment":
            return panel.content["Alignment"]
    raise AssertionError("Sector Alignment panel missing")


@pytest.mark.parametrize(
    ("rank", "score", "rotation", "quality", "expected"),
    [
        (1, 0.82, "STABLE", "COMPLETE", "STRONG"),
        (4, 0.50, "STABLE", "COMPLETE", "NEUTRAL"),
        (8, 0.20, "STABLE", "COMPLETE", "WEAK"),
        (4, 0.50, "IMPROVING", "COMPLETE", "IMPROVING"),
        (4, 0.50, "WEAKENING", "COMPLETE", "WEAKENING"),
        (1, 0.82, "IMPROVING", "PARTIAL", "INSUFFICIENT_DATA"),
    ],
)
def test_symbol_alignment_uses_only_persisted_snapshot_values(
    conn,
    rank: int,
    score: float,
    rotation: str,
    quality: str,
    expected: str,
) -> None:
    upsert_symbol(conn, "FPT", sector="Technology")
    upsert_sector_strength_snapshots(
        conn,
        [_sector_snapshot(rank=rank, score=score, rotation=rotation, quality=quality)],
    )

    result = _execute(conn, "/sector-strength FPT")

    assert _alignment_value(result) == expected


def test_symbol_alignment_discloses_unclassified_and_missing_snapshot_context(
    conn,
) -> None:
    upsert_symbol(conn, "VNM")
    upsert_symbol(conn, "HPG", sector="Materials")

    unclassified = _execute(conn, "/sector-strength VNM")
    missing_snapshot = _execute(conn, "/sector-strength HPG")

    assert _alignment_value(unclassified) == "INSUFFICIENT_DATA"
    assert _alignment_value(missing_snapshot) == "INSUFFICIENT_DATA"


def test_successful_market_regime_always_discloses_freshness_lineage_quality_and_caveats(
    conn,
) -> None:
    upsert_market_regime_snapshot(conn, _market_snapshot())

    result = _execute(conn, "/market-regime")
    panels = {panel.title: panel.content for panel in result.panels}

    assert {"Freshness", "Lineage", "Quality", "Data Caveats"} <= panels.keys()
    assert panels["Freshness"]["Benchmark bar date"] == "2026-07-01"
    assert panels["Lineage"]["source"] == "canonical"
    assert panels["Data Caveats"] == "No persisted data caveats."
    assert result.warnings == []


@pytest.mark.parametrize(
    "command",
    [
        "/sector-strength",
        "/sector-strength FPT",
        "/sector-strength FPT --date 2026-07-02",
    ],
)
def test_successful_sector_strength_always_discloses_full_context(
    conn, command: str
) -> None:
    snapshot = _sector_snapshot()
    upsert_sector_strength_snapshots(conn, [snapshot])
    upsert_symbol(conn, "FPT", sector="Technology")

    result = _execute(conn, command)
    panels = {panel.title: panel.content for panel in result.panels}

    assert {"Freshness", "Lineage", "Quality", "Data Caveats"} <= panels.keys()
    assert panels["Freshness"]["As of"] == "2026-07-02"
    assert panels["Lineage"] == dict(snapshot.lineage)
    assert panels["Quality"]["Methodology"] == snapshot.methodology_version
    assert panels["Data Caveats"] == "No persisted data caveats."
    assert result.warnings == []


def test_sector_strength_symbol_rejects_top_option(conn) -> None:
    result = _execute(conn, "/sector-strength FPT --top 1")

    assert result.status is CommandStatus.VALIDATION_ERROR
    assert result.error is not None
    assert result.error.error_type == "CommandValidationError"
    assert result.summary == "--top is only valid without a symbol."


def test_sector_strength_help_lists_mutually_exclusive_forms(conn) -> None:
    expected_usage = (
        "/sector-strength [--date YYYY-MM-DD] [--top N] | "
        "/sector-strength SYMBOL [--date YYYY-MM-DD]"
    )

    metadata = build_default_registry().get("sector-strength")
    help_result = _execute(conn, "/help")
    help_row = next(
        row for row in help_result.tables[0].rows if row[0] == "/sector-strength"
    )

    assert metadata.usage == expected_usage
    assert help_row[2] == expected_usage
