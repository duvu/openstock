"""Local tool adapters for persisted market and sector research context."""

from __future__ import annotations

import duckdb

from vnalpha.research_intelligence.context_repo import (
    get_market_regime_snapshot,
    get_ranked_sector_strength,
)
from vnalpha.research_intelligence.context_repo import (
    get_symbol_sector_alignment as get_persisted_symbol_sector_alignment,
)
from vnalpha.research_intelligence.regime import MarketRegimeBuilder
from vnalpha.research_intelligence.sector import SectorStrengthBuilder
from vnalpha.tools.models import ToolOutput


def get_market_regime(conn: duckdb.DuckDBPyConnection, date: str) -> ToolOutput:
    regime = get_market_regime_snapshot(conn, date)
    if regime is None:
        regime = MarketRegimeBuilder(conn).build(date)
    return ToolOutput(
        data=regime,
        summary=f"Market regime research context as of {date}.",
        warnings=regime["caveats"],
    )


def get_sector_strength(
    conn: duckdb.DuckDBPyConnection, date: str, top: int = 10
) -> ToolOutput:
    rankings = get_ranked_sector_strength(conn, date)
    if not rankings:
        rankings = SectorStrengthBuilder(conn).build(date)
    rankings = rankings[:top]
    warnings = [caveat for item in rankings for caveat in item["caveats"]]
    if not rankings:
        warnings.append("sector metadata or OHLCV history is unavailable")
    return ToolOutput(
        data=rankings,
        summary=f"Sector strength research context as of {date}.",
        warnings=sorted(set(warnings)),
    )


def get_symbol_sector_alignment(
    conn: duckdb.DuckDBPyConnection, symbol: str, date: str
) -> ToolOutput:
    rankings = get_ranked_sector_strength(conn, date)
    if not rankings:
        SectorStrengthBuilder(conn).build(date)
    alignment = get_persisted_symbol_sector_alignment(conn, symbol, date)
    return ToolOutput(
        data=alignment,
        summary=f"Sector alignment research context for {symbol} as of {date}.",
        warnings=alignment["caveats"],
    )
