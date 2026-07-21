from __future__ import annotations

import duckdb

from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.migrations import run_migrations

RESEARCH_TOOL_NAMES = {
    "analysis.deep_symbol",
    "market.get_regime",
    "sector.get_strength",
    "sector.get_symbol_alignment",
    "watchlist.summarize_deep",
    "shortlist.generate",
    "scenario.generate_research_plan",
    "evidence.get_setup_history",
}


def test_local_registry_exposes_all_bounded_research_tools():
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)

    registry = build_local_tool_registry(conn)

    assert RESEARCH_TOOL_NAMES.issubset(set(registry.names()))
    conn.close()
