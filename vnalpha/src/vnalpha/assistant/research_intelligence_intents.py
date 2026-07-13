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
        "create_indicator_experiment",
        "create_feature",
        "validate_feature",
        "test_hypothesis",
        "scan_pattern",
        "run_offline_event_study",
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
    {
        "generate_shortlist",
        "generate_research_scenario",
        "create_indicator_experiment",
        "create_feature",
        "validate_feature",
        "test_hypothesis",
        "scan_pattern",
        "run_offline_event_study",
    }
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
    "create_indicator_experiment": "reproducible indicator experiment on persisted Vietnamese equity data",
    "create_feature": "persist a research feature definition such as rs_20 = rs_20d_vs_vnindex",
    "validate_feature": "validate a research feature's schema, coverage, lineage, and quality",
    "test_hypothesis": "bounded historical hypothesis test with assumptions, metrics, and caveats",
    "scan_pattern": "scan persisted historical features for a supported research pattern",
    "run_offline_event_study": "offline research event study; never broker or live trading execution",
}

INTENT_EXAMPLES: Final[dict[str, str]] = {
    "deep_analyze_symbol": "Give me a deep research review of FPT.",
    "review_market_regime": "What was the market regime on 2026-07-01?",
    "review_sector_strength": "Show the strongest sectors today.",
    "summarize_watchlist_deep": "Summarize today's watchlist in depth.",
    "generate_shortlist": "Create a research shortlist from today's watchlist.",
    "generate_research_scenario": "Build a conditional research scenario for FPT.",
    "review_setup_evidence": "Show historical evidence for ACCUMULATION_BASE.",
    "create_indicator_experiment": "Test 20-session relative strength versus VNINDEX on VN30.",
    "create_feature": "Create feature rs_20 = rs_20d_vs_vnindex.",
    "validate_feature": "Validate the rs_20 research feature.",
    "test_hypothesis": "Test whether positive rs_20 has better 20-session returns.",
    "scan_pattern": "Scan VN30 for accumulation bases with volatility contraction.",
    "run_offline_event_study": "Run an offline event study for FPT accumulation breakouts.",
}


def classifier_lines() -> list[str]:
    """Return stable prompt lines for the classifier's supported-intent section."""
    return [
        f"- {name}: {description}" for name, description in INTENT_DESCRIPTIONS.items()
    ]
