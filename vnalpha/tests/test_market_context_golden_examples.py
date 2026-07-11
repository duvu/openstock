from __future__ import annotations

import duckdb

from vnalpha.warehouse.migrations import run_migrations


def _connection() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    return conn


def _seed_context(conn: duckdb.DuckDBPyConnection) -> None:
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
            ('AAA', '2025-01-31', '1D', 110, 111, 109, 110, 1000, 'PASS'),
            ('BBB', '2025-01-01', '1D', 100, 101, 99, 100, 1000, 'PASS'),
            ('BBB', '2025-01-31', '1D', 108, 109, 107, 108, 1000, 'PASS'),
            ('CCC', '2025-01-01', '1D', 100, 101, 99, 100, 1000, 'PASS'),
            ('CCC', '2025-01-31', '1D', 96, 97, 95, 96, 1000, 'PASS'),
            ('VNINDEX', '2025-01-01', '1D', 100, 101, 99, 100, 1000, 'PASS'),
            ('VNINDEX', '2025-01-31', '1D', 104, 105, 103, 104, 1000, 'PASS')
        """
    )


def test_market_context_golden_examples_are_research_only() -> None:
    from vnalpha.assistant.models import IntentResult
    from vnalpha.assistant.planner import PlanBuilder
    from vnalpha.research_intelligence.regime import MarketRegimeBuilder
    from vnalpha.research_intelligence.sector import SectorStrengthBuilder

    # Given: deterministic persisted market and sector inputs
    conn = _connection()
    _seed_context(conn)

    # When: builders and every market-context assistant intent are evaluated
    regime = MarketRegimeBuilder(conn).build("2025-01-31")
    sectors = SectorStrengthBuilder(conn).build("2025-01-31")
    plans = [
        PlanBuilder().build(
            IntentResult(intent=intent, confidence=1.0, entities={"symbol": "AAA"})
        )
        for intent in (
            "review_market_regime",
            "review_sector_strength",
            "review_symbol_sector_alignment",
        )
    ]

    # Then: golden context stays deterministic, traceable, and non-executing
    assert regime["state"] == "risk_on"
    assert regime["as_of_date"] == "2025-01-31"
    assert [sector["sector"] for sector in sectors] == ["Technology", "Financials"]
    assert [plan.steps[0].tool_name for plan in plans] == [
        "market.get_regime",
        "sector.get_strength",
        "sector.get_symbol_alignment",
    ]
    rendered = str({"regime": regime, "sectors": sectors}).lower()
    for forbidden in (
        "buy",
        "sell",
        "order",
        "allocation",
        "portfolio",
        "broker",
        "margin",
    ):
        assert forbidden not in rendered
