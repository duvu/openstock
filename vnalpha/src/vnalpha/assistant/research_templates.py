from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ResearchSynthesisTemplate:
    intent: str
    required_tools: tuple[str, ...]
    required_data_keys: tuple[str, ...]
    required_sections: tuple[str, ...]
    required_caveats: tuple[str, ...]
    require_research_marker: bool = False

    def to_prompt_dict(self) -> dict:
        return asdict(self)


_TEMPLATES: Mapping[str, ResearchSynthesisTemplate] = MappingProxyType(
    {
        "deep_analyze_symbol": ResearchSynthesisTemplate(
            intent="deep_analyze_symbol",
            required_tools=("analysis.deep_symbol",),
            required_data_keys=(
                "status",
                "symbol",
                "as_of_date",
                "technical_context",
                "levels",
                "quality",
                "caveats",
                "missing_data",
            ),
            required_sections=(
                "trend and momentum context",
                "relative strength and participation",
                "levels and setup quality",
                "data quality and missing evidence",
            ),
            required_caveats=(
                "descriptive persisted research context",
                "data completeness limits confidence",
            ),
            require_research_marker=True,
        ),
        "review_market_regime": ResearchSynthesisTemplate(
            intent="review_market_regime",
            required_tools=("market.get_regime",),
            required_data_keys=(),
            required_sections=("regime", "breadth", "freshness and methodology"),
            required_caveats=("persisted context is descriptive, not predictive",),
        ),
        "review_sector_strength": ResearchSynthesisTemplate(
            intent="review_sector_strength",
            required_tools=("sector.get_strength",),
            required_data_keys=(),
            required_sections=("ranked sectors", "coverage and quality", "caveats"),
            required_caveats=("ranking depends on available sector metadata",),
        ),
        "review_symbol_sector_alignment": ResearchSynthesisTemplate(
            intent="review_symbol_sector_alignment",
            required_tools=("sector.get_symbol_alignment",),
            required_data_keys=(),
            required_sections=("persisted sector metadata", "alignment context", "caveats"),
            required_caveats=("do not infer missing sector metadata",),
        ),
        "summarize_watchlist_deep": ResearchSynthesisTemplate(
            intent="summarize_watchlist_deep",
            required_tools=("watchlist.summarize_deep",),
            required_data_keys=(
                "status",
                "as_of_date",
                "candidate_count",
                "class_distribution",
                "setup_distribution",
                "caveats",
                "missing_data",
            ),
            required_sections=(
                "watchlist structure",
                "research focus groups",
                "risk and data-quality review",
            ),
            required_caveats=("watchlist ranking is a screening artifact",),
            require_research_marker=True,
        ),
        "generate_shortlist": ResearchSynthesisTemplate(
            intent="generate_shortlist",
            required_tools=("shortlist.generate",),
            required_data_keys=(
                "status",
                "as_of_date",
                "methodology",
                "candidates",
                "caveats",
                "missing_data",
            ),
            required_sections=(
                "why each name remains on the research agenda",
                "confirmation still required",
                "risks and exclusions",
            ),
            required_caveats=(
                "shortlist is a research prioritization artifact",
                "human review remains required",
            ),
            require_research_marker=True,
        ),
        "generate_research_scenario": ResearchSynthesisTemplate(
            intent="generate_research_scenario",
            required_tools=("scenario.generate_research_plan",),
            required_data_keys=(
                "status",
                "symbol",
                "as_of_date",
                "scenarios",
                "policy_status",
                "caveats",
                "missing_data",
            ),
            required_sections=(
                "base case",
                "confirmation case",
                "failed confirmation case",
                "monitoring checklist and caveats",
            ),
            required_caveats=(
                "conditional research scenario only",
                "future confirmation is required",
            ),
            require_research_marker=True,
        ),
        "review_setup_evidence": ResearchSynthesisTemplate(
            intent="review_setup_evidence",
            required_tools=("evidence.get_setup_history",),
            required_data_keys=(
                "status",
                "setup_type",
                "horizon_sessions",
                "sample_size",
                "methodology_version",
                "caveats",
                "missing_data",
            ),
            required_sections=("sample", "historical outcomes", "methodology and caveats"),
            required_caveats=(
                "historical observations are not predictions",
                "small samples require restraint",
            ),
            require_research_marker=True,
        ),
    }
)

RESEARCH_INTELLIGENCE_INTENTS = frozenset(_TEMPLATES)
STRICT_POLICY_INTENTS = frozenset({"generate_shortlist", "generate_research_scenario"})


def get_research_template(intent: str) -> ResearchSynthesisTemplate | None:
    return _TEMPLATES.get(intent)


def is_research_intelligence_intent(intent: str) -> bool:
    return intent in RESEARCH_INTELLIGENCE_INTENTS


def research_template_prompt(intent: str) -> dict | None:
    template = get_research_template(intent)
    return template.to_prompt_dict() if template is not None else None


__all__ = [
    "RESEARCH_INTELLIGENCE_INTENTS",
    "STRICT_POLICY_INTENTS",
    "ResearchSynthesisTemplate",
    "get_research_template",
    "is_research_intelligence_intent",
    "research_template_prompt",
]
