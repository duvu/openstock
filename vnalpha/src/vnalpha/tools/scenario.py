"""Local-tool adapter for deterministic research scenario plans."""

from __future__ import annotations

import duckdb

from vnalpha.research_intelligence.scenario_plan import ScenarioPlanBuilder
from vnalpha.tools.models import ToolOutput


def generate_research_plan(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
    with_evidence: bool = False,
    with_regime: bool = False,
    correlation_id: str | None = None,
) -> ToolOutput:
    """Generate a persisted research-only scenario plan for one symbol."""
    plan = ScenarioPlanBuilder(conn).build(
        symbol,
        date,
        with_evidence=with_evidence,
        with_regime=with_regime,
        correlation_id=correlation_id,
    )
    return ToolOutput(
        data=plan,
        summary=f"Research scenario plan for {symbol} as of {date}.",
        warnings=plan["caveats"],
    )
