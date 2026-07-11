from __future__ import annotations

import uuid
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vnalpha.assistant.models import AssistantPlan, IntentResult, ToolPlanStep


@dataclass(frozen=True, slots=True)
class ResearchIntentDefinition:
    intent: str
    description: str
    tool_name: str
    permission: str
    required_artifacts: tuple[str, ...]
    example: str


RESEARCH_INTENT_DEFINITIONS: Mapping[str, ResearchIntentDefinition] = MappingProxyType(
    {
        "deep_analyze_symbol": ResearchIntentDefinition(
            "deep_analyze_symbol",
            "full warehouse-grounded review of one symbol",
            "analysis.deep_symbol",
            "READ_SCORE",
            ("candidate_score", "feature_snapshot", "canonical_ohlcv"),
            "Give me a deep research review of FPT.",
        ),
        "review_market_regime": ResearchIntentDefinition(
            "review_market_regime",
            "persisted market regime context",
            "market.get_regime",
            "READ_FEATURES",
            ("market_regime_snapshot",),
            "Review the market regime for today.",
        ),
        "review_sector_strength": ResearchIntentDefinition(
            "review_sector_strength",
            "persisted ranked sector context",
            "sector.get_strength",
            "READ_FEATURES",
            ("sector_strength_snapshot",),
            "Which sectors have the strongest persisted context?",
        ),
        "summarize_watchlist_deep": ResearchIntentDefinition(
            "summarize_watchlist_deep",
            "structured watchlist synthesis and risk review",
            "watchlist.summarize_deep",
            "READ_WATCHLIST",
            ("daily_watchlist", "candidate_score", "feature_snapshot"),
            "Summarize today's watchlist deeply.",
        ),
        "generate_shortlist": ResearchIntentDefinition(
            "generate_shortlist",
            "deterministic research-priority shortlist",
            "shortlist.generate",
            "READ_WATCHLIST",
            ("daily_watchlist", "candidate_score", "feature_snapshot"),
            "Create a five-name research shortlist for today.",
        ),
        "generate_research_scenario": ResearchIntentDefinition(
            "generate_research_scenario",
            "conditional, research-only scenario map for one symbol",
            "scenario.generate_research_plan",
            "READ_SCORE",
            ("candidate_score", "feature_snapshot", "canonical_ohlcv"),
            "Create a conditional research scenario for FPT.",
        ),
        "review_setup_evidence": ResearchIntentDefinition(
            "review_setup_evidence",
            "historical persisted outcome evidence for a setup or symbol",
            "evidence.get_setup_history",
            "READ_HISTORY",
            ("candidate_outcome", "setup_type_performance"),
            "Review historical evidence for ACCUMULATION_BASE.",
        ),
    }
)

RESEARCH_INTELLIGENCE_INTENTS = frozenset(RESEARCH_INTENT_DEFINITIONS)


def classifier_prompt_lines() -> tuple[str, ...]:
    return tuple(
        f"- {definition.intent}: {definition.description}"
        for definition in RESEARCH_INTENT_DEFINITIONS.values()
    )


def classifier_examples() -> tuple[str, ...]:
    return tuple(
        f'- "{definition.example}" -> {definition.intent}'
        for definition in RESEARCH_INTENT_DEFINITIONS.values()
    )


def build_research_intelligence_plan(intent_result: IntentResult) -> AssistantPlan | None:
    definition = RESEARCH_INTENT_DEFINITIONS.get(intent_result.intent)
    if definition is None:
        return None
    args = _arguments_for_intent(intent_result.intent, intent_result.entities)
    step = ToolPlanStep(
        step_id=str(uuid.uuid4())[:8],
        tool_name=definition.tool_name,
        arguments=args,
        purpose=definition.description,
        required_permission=definition.permission,
    )
    return AssistantPlan(
        intent=intent_result.intent,
        steps=[step],
        assumptions=[
            "Only persisted warehouse data and deterministic tool output are authoritative."
        ],
        required_artifacts=list(definition.required_artifacts),
    )


def _arguments_for_intent(intent: str, entities: Mapping[str, Any]) -> dict[str, Any]:
    args: dict[str, Any] = {}
    date = entities.get("date")
    if date:
        args["date"] = date

    if intent in {"deep_analyze_symbol", "generate_research_scenario"}:
        symbol = _first_symbol(entities)
        if symbol:
            args["symbol"] = symbol
    elif intent == "review_sector_strength":
        if entities.get("top") is not None:
            args["top"] = entities["top"]
    elif intent == "generate_shortlist":
        args["limit"] = entities.get("limit", entities.get("top", 5))
        if entities.get("setup") or entities.get("setup_type"):
            args["setup"] = entities.get("setup") or entities.get("setup_type")
        if entities.get("sector"):
            args["sector"] = entities["sector"]
    elif intent == "review_setup_evidence":
        symbol = _first_symbol(entities)
        if symbol:
            args["symbol"] = symbol
        if entities.get("setup") or entities.get("setup_type"):
            args["setup_type"] = entities.get("setup") or entities.get("setup_type")
        args["horizon"] = entities.get("horizon", entities.get("horizon_sessions", 20))

    if intent == "generate_research_scenario":
        args["with_evidence"] = bool(entities.get("with_evidence", False))
        args["with_regime"] = bool(entities.get("with_regime", True))
    return args


def _first_symbol(entities: Mapping[str, Any]) -> str:
    symbol = entities.get("symbol")
    if symbol:
        return str(symbol)
    symbols = entities.get("symbols")
    if isinstance(symbols, (list, tuple)) and symbols:
        return str(symbols[0])
    return ""


__all__ = [
    "RESEARCH_INTELLIGENCE_INTENTS",
    "RESEARCH_INTENT_DEFINITIONS",
    "ResearchIntentDefinition",
    "build_research_intelligence_plan",
    "classifier_examples",
    "classifier_prompt_lines",
]
