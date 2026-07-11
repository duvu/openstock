"""Canonical taxonomy for deep research-intelligence assistant workflows."""

from __future__ import annotations

from typing import Final

RESEARCH_INTELLIGENCE_INTENTS: Final[frozenset[str]] = frozenset(
    {
        "deep_analyze_symbol",
        "review_market_regime",
        "review_sector_strength",
        "summarize_watchlist_deep",
        "generate_shortlist",
        "generate_research_scenario",
        "review_setup_evidence",
    }
)

DEEP_RESEARCH_INTENTS: Final[frozenset[str]] = frozenset(
    {
        "deep_analyze_symbol",
        "summarize_watchlist_deep",
        "generate_shortlist",
        "generate_research_scenario",
        "review_setup_evidence",
    }
)

POLICY_SENSITIVE_RESEARCH_INTENTS: Final[frozenset[str]] = frozenset(
    {"generate_shortlist", "generate_research_scenario"}
)

INTENT_DESCRIPTIONS: Final[dict[str, str]] = {
    "deep_analyze_symbol": (
        "deep, warehouse-grounded review of one symbol including score, features, "
        "levels, market/sector context, freshness, lineage, and caveats"
    ),
    "review_market_regime": "persisted market-regime research context",
    "review_sector_strength": "persisted ranked sector-strength research context",
    "summarize_watchlist_deep": (
        "structured synthesis of watchlist classes, setups, sectors, quality, and risks"
    ),
    "generate_shortlist": (
        "deterministic research shortlist ranked from persisted scores and context"
    ),
    "generate_research_scenario": (
        "conditional research scenario for one symbol; never execution guidance"
    ),
    "review_setup_evidence": (
        "historical persisted outcome evidence for a setup type and horizon"
    ),
}

INTENT_EXAMPLES: Final[dict[str, str]] = {
    "deep_analyze_symbol": "Give me a deep research review of FPT.",
    "review_market_regime": "What was the market regime on 2026-07-01?",
    "review_sector_strength": "Show the strongest sectors today.",
    "summarize_watchlist_deep": "Summarize today's watchlist in depth.",
    "generate_shortlist": "Create a research shortlist from today's watchlist.",
    "generate_research_scenario": "Build a conditional research scenario for FPT.",
    "review_setup_evidence": "Show historical evidence for ACCUMULATION_BASE.",
}


def classifier_lines() -> list[str]:
    """Return stable prompt lines for the classifier's supported-intent section."""
    return [
        f"- {name}: {description}"
        for name, description in INTENT_DESCRIPTIONS.items()
    ]
