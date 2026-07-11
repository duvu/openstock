from __future__ import annotations

from datetime import date, datetime, timezone
from io import StringIO

import duckdb
import pytest
from rich.console import Console

from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.models import CommandStatus
from vnalpha.commands.renderers.rich_renderer import render_result
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


def test_market_regime_absence_is_research_context_empty_result(conn) -> None:
    result = _execute(conn, "/market-regime --date 2026-07-01")

    assert result.status is CommandStatus.EMPTY_RESULT
    assert "persisted research context" in (result.summary or "").lower()


def test_market_regime_omits_tui_default_date_to_read_latest_snapshot(conn) -> None:
    upsert_market_regime_snapshot(conn, _regime_snapshot(date(2026, 7, 1)))
    upsert_market_regime_snapshot(conn, _regime_snapshot(date(2026, 7, 2)))

    result = CommandExecutor(
        conn, surface="tui-chat", default_date="2026-07-01"
    ).execute("/market-regime")

    assert result.status is CommandStatus.PARTIAL
    assert result.panels[0].content["As of"] == "2026-07-02"


@pytest.mark.parametrize(
    "command",
    [
        "/market-regime --date not-a-date",
        "/market-regime --date",
        "/sector-strength A B",
        "/sector-strength --top 0",
        "/sector-strength --top nope",
    ],
)
def test_research_context_commands_validate_dates_positionals_and_top(
    conn, command: str
) -> None:
    result = _execute(conn, command)

    assert result.status is CommandStatus.VALIDATION_ERROR


def test_sector_strength_lists_deterministic_persisted_rows_and_top(conn) -> None:
    as_of_date = date(2026, 7, 2)
    financials = _sector_snapshot(as_of_date, "Financials", 1)
    technology = _sector_snapshot(as_of_date, "Technology", 1)
    industrials = _sector_snapshot(as_of_date, "Industrials", 2)
    upsert_sector_strength_snapshots(conn, (industrials, technology, financials))

    result = _execute(conn, "/sector-strength --top 2")

    assert result.status is CommandStatus.PARTIAL
    assert [row[1] for row in result.tables[0].rows] == ["Financials", "Technology"]
    assert [column.name for column in result.tables[0].columns] == [
        "rank",
        "sector",
        "score",
        "return20",
        "rs20",
        "breadth_ma20",
        "breadth_ma50",
        "members",
        "eligible",
        "coverage",
        "rotation",
        "quality",
    ]
    assert financials.caveats[0] in result.warnings
    assert "research context" in (result.summary or "").lower()


def test_sector_strength_symbol_uses_persisted_alignment_and_discloses_gaps(
    conn,
) -> None:
    as_of_date = date(2026, 7, 2)
    snapshot = _sector_snapshot(as_of_date, "Technology", 1)
    upsert_sector_strength_snapshots(conn, (snapshot,))
    upsert_symbol(conn, "FPT", sector="Technology")
    upsert_symbol(conn, "VNM")
    upsert_symbol(conn, "HPG", sector="Materials")

    aligned = _execute(conn, "/sector-strength FPT --date 2026-07-02")
    no_metadata = _execute(conn, "/sector-strength VNM")
    no_snapshot = _execute(conn, "/sector-strength HPG --date 2026-07-02")
    unknown = _execute(conn, "/sector-strength UNKNOWN")

    assert aligned.status is CommandStatus.PARTIAL
    assert any("Technology" in str(panel.content) for panel in aligned.panels)
    assert snapshot.caveats[0] in aligned.warnings
    assert no_metadata.status is CommandStatus.EMPTY_RESULT
    assert any("metadata" in warning.lower() for warning in no_metadata.warnings)
    assert no_snapshot.status is CommandStatus.EMPTY_RESULT
    assert any("snapshot" in warning.lower() for warning in no_snapshot.warnings)
    assert unknown.status is CommandStatus.EMPTY_RESULT
    assert any("metadata" in warning.lower() for warning in unknown.warnings)


def test_research_context_commands_register_with_read_permissions_and_help(
    conn,
) -> None:
    registry = build_default_registry()

    assert registry.get("market-regime").permissions == ["READ_FEATURES"]
    assert registry.get("sector-strength").permissions == ["READ_FEATURES"]
    assert registry.get("market-regime").examples == [
        "/market-regime",
        "/market-regime --date 2026-07-06",
    ]
    assert (
        "/sector-strength FPT --date 2026-07-06"
        in registry.get("sector-strength").examples
    )
    help_result = _execute(conn, "/help")
    help_commands = [row[0] for row in help_result.tables[0].rows]

    assert "/market-regime" in help_commands
    assert "/sector-strength" in help_commands

    from vnalpha.chat.controller import ChatController

    chat_help = ChatController(on_message=lambda _style, _text: None)._cmd_help()
    assert "/market-regime" in chat_help
    assert "/sector-strength" in chat_help


def test_market_regime_semantic_result_renders_panels_and_warnings(conn) -> None:
    upsert_market_regime_snapshot(conn, _regime_snapshot(date(2026, 7, 2)))

    result = _execute(conn, "/market-regime")
    output = StringIO()
    render_result(result, Console(file=output, highlight=False))

    assert "Regime" in output.getvalue()
    assert "Coverage excludes inactive symbols." in output.getvalue()
