"""Public facade for deterministic research-intelligence tools.

The implementations are intentionally split by domain so assistant integration does
not recreate a monolithic tool module.
"""

from vnalpha.tools.research_evidence import get_setup_history
from vnalpha.tools.research_scenario import generate_research_scenario
from vnalpha.tools.research_symbol import deep_symbol_analysis
from vnalpha.tools.research_watchlist import generate_shortlist, summarize_watchlist_deep

__all__ = [
    "deep_symbol_analysis",
    "generate_research_scenario",
    "generate_shortlist",
    "get_setup_history",
    "summarize_watchlist_deep",
]
