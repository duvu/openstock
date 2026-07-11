"""Local tool adapter for warehouse-grounded deep symbol analysis."""

from __future__ import annotations

import duckdb

from vnalpha.research_intelligence.deep_analysis import DeepAnalysisBuilder
from vnalpha.tools.models import ToolOutput


def deep_analyze_symbol(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
    with_sector: bool = False,
    with_regime: bool = False,
) -> ToolOutput:
    """Return persisted-artifact research context without an execution recommendation."""
    analysis = DeepAnalysisBuilder(conn).build(symbol, date, with_sector, with_regime)
    return ToolOutput(
        data=analysis,
        summary=f"Deep research analysis for {symbol} as of {date}.",
        warnings=analysis["missing_data"],
    )
