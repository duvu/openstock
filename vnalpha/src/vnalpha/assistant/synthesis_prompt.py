from __future__ import annotations

import json
from typing import Any

from vnalpha.assistant.context import build_context_message
from vnalpha.assistant.groundedness import available_source_refs
from vnalpha.assistant.models import AssistantPlan, AssistantRequest
from vnalpha.assistant.policy import OUTPUT_EXECUTION_PHRASES
from vnalpha.assistant.research_templates import research_prompt_fragment
from vnalpha.model_routing.models import ModelTaskType

CONTEXT_INTENT_DISCLOSURES = {
    "review_market_regime": (
        "Describe the persisted market-regime snapshot, its methodology version, "
        "benchmark freshness, quality, lineage, and caveats."
    ),
    "review_sector_strength": (
        "Describe persisted sector ranking order, methodology version, freshness, "
        "quality or coverage, lineage, and caveats."
    ),
    "review_symbol_sector_alignment": (
        "Describe only persisted symbol metadata and matching sector snapshot; state "
        "missing metadata or snapshot context without inference."
    ),
}

CONTEXT_INTENTS = frozenset(CONTEXT_INTENT_DISCLOSURES)
UNSAFE_CONTEXT_TERMS = OUTPUT_EXECUTION_PHRASES | frozenset(
    {
        "rebalance",
        "position",
        "invest",
        "purchase",
        "allocate",
        "allocation",
        "margin",
    }
)

SYNTHESIS_RESPONSE_SCHEMA: dict[str, Any] = {
    "title": "vnalpha_grounded_answer",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "basis",
        "risks_caveats",
        "tool_trace_summary",
        "missing_data",
        "grounded_source_refs",
        "claim_source_refs",
        "research_metadata",
    ],
    "properties": {
        "summary": {"type": "string"},
        "basis": {"type": "string"},
        "risks_caveats": {"type": "string"},
        "tool_trace_summary": {"type": "string"},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "grounded_source_refs": {"type": "array", "items": {"type": "string"}},
        "claim_source_refs": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
        "research_metadata": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
    },
}

SYNTHESIZER_SYSTEM_PROMPT = """You are a research assistant for a Vietnamese stock market screening tool.

Your role is to explain deterministic pipeline outputs as persisted research context.

STRICT RULES:
1. Use only the supplied tool outputs as factual data.
2. MUST NOT override persisted scores, classes, setup types, quality, lineage, or methodology.
3. Do not give action guidance, personalized advice, or execution instructions.
4. Do not claim certainty or guaranteed future outcomes.
5. State missing, partial, stale, or unavailable evidence explicitly.
6. Include basis, freshness, methodology, quality, lineage, risks, caveats, and missing data when available.
7. Follow the supplied research template for research-intelligence intents.
8. Use only values listed in valid_grounded_source_refs for grounded_source_refs.
9. Return claim_source_refs and research_metadata as empty objects; validation metadata is added by the application.
10. Shortlist and scenario outputs are research-prioritization artifacts requiring human review.

Respond only with JSON matching the supplied response schema.
"""


def _build_synthesis_messages(
    user_prompt: str,
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
    request: AssistantRequest | None = None,
) -> list[dict]:
    context = {
        "user_question": user_prompt,
        "intent": plan.intent,
        "required_artifacts": plan.required_artifacts,
        "context_intent_disclosure": CONTEXT_INTENT_DISCLOSURES.get(plan.intent),
        "research_template": research_prompt_fragment(plan.intent),
        "valid_grounded_source_refs": available_source_refs(plan, tool_outputs),
        "tool_outputs": tool_outputs,
    }
    messages = [{"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT}]
    if request is not None:
        context_message = build_context_message(request)
        if context_message is not None:
            messages.append(context_message)
    messages.append(
        {
            "role": "user",
            "content": json.dumps(context, default=str, ensure_ascii=False),
        }
    )
    return messages


def _symbol_count(plan: AssistantPlan) -> int:
    symbols: set[str] = set()
    for step in plan.steps:
        value = step.arguments.get("symbol")
        if value:
            symbols.add(str(value))
        values = step.arguments.get("symbols")
        if isinstance(values, (list, tuple, set)):
            symbols.update(str(item) for item in values if item)
    return len(symbols)


def task_type_for_plan(plan: AssistantPlan) -> str:
    mapping = {
        "summarize_watchlist": ModelTaskType.WATCHLIST_SUMMARY.value,
        "summarize_watchlist_deep": ModelTaskType.WATCHLIST_SUMMARY.value,
        "compare_symbols": ModelTaskType.MULTI_SYMBOL_COMPARISON.value,
        "deep_analyze_symbol": ModelTaskType.DEEP_SYMBOL_ANALYSIS.value,
        "generate_shortlist": ModelTaskType.SHORTLIST_GENERATION.value,
        "generate_research_scenario": ModelTaskType.RESEARCH_SCENARIO.value,
        "review_setup_evidence": ModelTaskType.DEEP_SYMBOL_ANALYSIS.value,
    }
    return mapping.get(plan.intent, ModelTaskType.NORMAL_ANSWER.value)
