from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.warehouse.migrations import run_migrations


def _connection() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    return conn


def _seed_market_context(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        INSERT INTO symbol_master (symbol, sector) VALUES
            ('AAA', 'Technology'), ('BBB', 'Technology'), ('CCC', 'Financials'),
            ('VNINDEX', 'Index')
        """
    )
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume, quality_status)
        VALUES
            ('AAA', '2025-01-01', '1D', 100, 101, 99, 100, 1000, 'PASS'),
            ('AAA', '2025-01-31', '1D', 110, 112, 109, 110, 1200, 'PASS'),
            ('BBB', '2025-01-01', '1D', 100, 101, 99, 100, 1000, 'PASS'),
            ('BBB', '2025-01-31', '1D', 108, 110, 107, 108, 1200, 'PASS'),
            ('CCC', '2025-01-01', '1D', 100, 101, 99, 100, 1000, 'PASS'),
            ('CCC', '2025-01-31', '1D', 96, 98, 95, 96, 900, 'PASS'),
            ('VNINDEX', '2025-01-01', '1D', 100, 101, 99, 100, 1000, 'PASS'),
            ('VNINDEX', '2025-01-31', '1D', 104, 105, 103, 104, 1000, 'PASS')
        """
    )


def test_market_regime_persists_research_context() -> None:
    from vnalpha.research_intelligence.regime import MarketRegimeBuilder

    conn = _connection()
    _seed_market_context(conn)

    result = MarketRegimeBuilder(conn).build("2025-01-31")

    assert result["as_of_date"] == "2025-01-31"
    assert result["state"] in {"risk_on", "constructive", "mixed", "risk_off"}
    assert result["breadth"]["advancing_symbols"] == 2
    assert (
        conn.execute("SELECT count(*) FROM market_regime_snapshot").fetchone()[0] == 1
    )


def test_sector_strength_ranks_sectors_and_aligns_symbols() -> None:
    from vnalpha.research_intelligence.sector import SectorStrengthBuilder

    conn = _connection()
    _seed_market_context(conn)

    rankings = SectorStrengthBuilder(conn).build("2025-01-31")
    alignment = SectorStrengthBuilder(conn).symbol_alignment("AAA", "2025-01-31")

    assert rankings[0]["sector"] == "Technology"
    assert rankings[0]["rotation"] == "improving"
    assert alignment["alignment"] == "strong"
    assert (
        conn.execute("SELECT count(*) FROM sector_strength_snapshot").fetchone()[0] == 2
    )


def test_sector_strength_includes_research_metadata() -> None:
    from vnalpha.research_intelligence.sector import SectorStrengthBuilder

    # Given: canonical data and sector metadata are available as of the requested date
    conn = _connection()
    _seed_market_context(conn)

    # When: persisted sector strength context is built
    sectors = SectorStrengthBuilder(conn).build("2025-01-31")

    # Then: every sector snapshot carries its evidence and quality context
    technology = next(item for item in sectors if item["sector"] == "Technology")
    assert technology["freshness"] == "AS_OF_DATE"
    assert technology["lineage"] == {
        "benchmark": "VNINDEX",
        "source": "canonical_ohlcv",
    }
    assert technology["quality"] == "complete"
    assert "sector_strength_v1" in technology["methodology"]


def test_sector_strength_marks_flat_returns_as_stable() -> None:
    from vnalpha.research_intelligence.sector import SectorStrengthBuilder

    # Given: sector constituents with no observed return across the available window
    conn = _connection()
    _seed_market_context(conn)
    conn.execute(
        "UPDATE canonical_ohlcv SET close = 100.0 WHERE symbol IN ('AAA', 'BBB', 'CCC') AND time = '2025-01-31'"
    )

    # When: sector strength is calculated
    sectors = SectorStrengthBuilder(conn).build("2025-01-31")

    # Then: flat median returns produce a stable rotation state
    assert {sector["rotation"] for sector in sectors} == {"stable"}


def test_sector_strength_tool_discloses_missing_sector_data() -> None:
    from vnalpha.tools.market_context import get_sector_strength

    # Given: no sector metadata or canonical history is available
    conn = _connection()

    # When: sector research context is requested
    output = get_sector_strength(conn, "2025-01-31")

    # Then: the empty result remains caveated rather than implying sector coverage
    assert output.data == []
    assert output.warnings == ["sector metadata or OHLCV history is unavailable"]


def test_market_context_discloses_missing_benchmark() -> None:
    from vnalpha.research_intelligence.regime import MarketRegimeBuilder

    conn = _connection()

    result = MarketRegimeBuilder(conn).build("2025-01-31")

    assert result["state"] == "insufficient_data"
    assert "VNINDEX benchmark data is unavailable" in result["caveats"]


def test_market_regime_reports_benchmark_volatility_and_methodology_version() -> None:
    from vnalpha.research_intelligence.regime import MarketRegimeBuilder

    conn = _connection()
    _seed_market_context(conn)
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume, quality_status)
        VALUES ('VNINDEX', '2025-01-15', '1D', 104, 105, 103, 104, 1000, 'PASS')
        """
    )

    result = MarketRegimeBuilder(conn).build("2025-01-31")

    assert result["volatility"] == "elevated"
    assert "market_regime_v1" in result["methodology"]
    assert result["quality"] == "complete"


def test_sector_strength_uses_median_return() -> None:
    from vnalpha.research_intelligence.sector import SectorStrengthBuilder

    conn = _connection()
    _seed_market_context(conn)
    conn.execute(
        "UPDATE canonical_ohlcv SET close = 130.0 WHERE symbol = 'AAA' AND time = '2025-01-31'"
    )
    conn.execute(
        "INSERT INTO symbol_master (symbol, sector) VALUES ('DDD', 'Technology')"
    )
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume, quality_status)
        VALUES
            ('DDD', '2025-01-01', '1D', 100, 101, 99, 100, 1000, 'PASS'),
            ('DDD', '2025-01-31', '1D', 105, 106, 104, 105, 1000, 'PASS')
        """
    )

    sector = SectorStrengthBuilder(conn).build("2025-01-31")[0]

    assert sector["median_return"] == pytest.approx(0.08)


def test_market_context_is_exposed_through_commands_tools_and_assistant() -> None:
    from vnalpha.assistant.models import IntentResult
    from vnalpha.assistant.planner import PlanBuilder
    from vnalpha.commands.setup import build_default_registry
    from vnalpha.tools.setup import build_local_tool_registry

    conn = _connection()

    assert {"market-regime", "sector-strength"} <= set(build_default_registry().names())
    assert {
        "market.get_regime",
        "sector.get_strength",
        "sector.get_symbol_alignment",
    } <= set(build_local_tool_registry(conn).names())
    assert [
        step.tool_name
        for step in PlanBuilder()
        .build(
            IntentResult(
                intent="review_market_regime",
                confidence=1.0,
                entities={"date": "2025-01-31"},
            )
        )
        .steps
    ] == ["market.get_regime"]


def test_market_context_commands_render_research_panels() -> None:
    from vnalpha.commands.parser import parse
    from vnalpha.commands.setup import build_default_registry
    from vnalpha.tools.executor import TracedLocalToolExecutor
    from vnalpha.tools.setup import build_local_tool_registry

    # Given: persisted market inputs and the standard command execution surface
    conn = _connection()
    _seed_market_context(conn)
    registry = build_default_registry()
    executor = TracedLocalToolExecutor(
        conn,
        build_local_tool_registry(conn),
        session_id="market-context-command-test",
    )

    # When: the market and symbol-sector research commands are executed
    regime = registry.execute(
        parse("/market-regime --date 2025-01-31"),
        conn=conn,
        registry=registry,
        tool_executor=executor,
    )
    sector = registry.execute(
        parse("/sector-strength AAA --date 2025-01-31"),
        conn=conn,
        registry=registry,
        tool_executor=executor,
    )

    # Then: each response renders context and caveats without an execution action
    assert [panel.title for panel in regime.panels] == ["Market Regime", "Caveats"]
    assert [panel.title for panel in sector.panels] == [
        "Sector Strength",
        "Symbol Alignment",
        "Caveats",
    ]


def test_market_context_builders_emit_correlated_events(tmp_path) -> None:
    from vnalpha.observability.context import RunContext, set_correlation_id
    from vnalpha.research_intelligence.regime import MarketRegimeBuilder
    from vnalpha.research_intelligence.sector import SectorStrengthBuilder

    # Given: a run context with persisted market inputs and a correlation ID
    conn = _connection()
    _seed_market_context(conn)
    run_ctx = RunContext(
        run_id="market-context-test",
        surface="cli",
        actor="test",
        log_root=tmp_path,
    )
    correlation_id = set_correlation_id()

    # When: regime and sector snapshots are built
    MarketRegimeBuilder(conn).build("2025-01-31", run_ctx=run_ctx)
    SectorStrengthBuilder(conn).build("2025-01-31", run_ctx=run_ctx)

    # Then: each emitted audit event keeps the active correlation ID
    events = [
        json.loads(line)
        for line in run_ctx.audit_path.read_text().splitlines()
        if line.strip()
    ]
    event_types = {event["event_type"] for event in events}
    assert {"MARKET_REGIME_BUILT", "SECTOR_STRENGTH_BUILT"} <= event_types
    assert all(event["correlation_id"] == correlation_id for event in events)


def test_market_context_repositories_return_persisted_as_of_snapshots() -> None:
    from vnalpha.research_intelligence.context_repo import (
        get_market_regime_snapshot,
        get_ranked_sector_strength,
        get_symbol_sector_alignment,
    )
    from vnalpha.research_intelligence.regime import MarketRegimeBuilder
    from vnalpha.research_intelligence.sector import SectorStrengthBuilder

    # Given: persisted market and sector context for a known date
    conn = _connection()
    _seed_market_context(conn)
    MarketRegimeBuilder(conn).build("2025-01-31")
    SectorStrengthBuilder(conn).build("2025-01-31")

    # When: repository APIs retrieve the date's stored snapshots
    regime = get_market_regime_snapshot(conn, "2025-01-31")
    sectors = get_ranked_sector_strength(conn, "2025-01-31")
    alignment = get_symbol_sector_alignment(conn, "AAA", "2025-01-31")

    # Then: regime, ranked sectors, and symbol alignment remain research context
    assert regime is not None and regime["as_of_date"] == "2025-01-31"
    assert [sector["rank"] for sector in sectors] == [1, 2]
    assert alignment["alignment"] == "strong"


def test_market_context_tools_read_persisted_snapshots() -> None:
    from vnalpha.research_intelligence.regime import MarketRegimeBuilder
    from vnalpha.research_intelligence.sector import SectorStrengthBuilder
    from vnalpha.tools.market_context import (
        get_market_regime,
        get_sector_strength,
        get_symbol_sector_alignment,
    )

    # Given: snapshots already persisted for the requested date
    conn = _connection()
    _seed_market_context(conn)
    MarketRegimeBuilder(conn).build("2025-01-31")
    SectorStrengthBuilder(conn).build("2025-01-31")
    conn.execute("DELETE FROM canonical_ohlcv")

    # When: research tools load the requested context
    regime = get_market_regime(conn, "2025-01-31")
    sectors = get_sector_strength(conn, "2025-01-31")
    alignment = get_symbol_sector_alignment(conn, "AAA", "2025-01-31")

    # Then: persisted state remains available without reconstructing from deleted bars
    assert regime.data["state"] == "risk_on"
    assert regime.data["quality"] == "partial"
    assert sectors.data[0]["sector"] == "Technology"
    assert alignment.data["alignment"] == "strong"
