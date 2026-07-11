"""
AnswerSynthesizer: grounds final assistant responses in deterministic tool outputs.

Research-intelligence answers pass a structured pre-synthesis payload check and a
post-synthesis claim/policy check. Tool outputs remain the source of truth.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.groundedness import (
    GroundednessResult,
    assert_grounded,
    validate_research_answer,
    validate_tool_grounding,
)
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.assistant.policy import TRADING_EXECUTION_PHRASES
from vnalpha.assistant.research_templates import research_template_prompt
from vnalpha.assistant.response_parser import parse_synthesis_response
from vnalpha.model_routing.models import ModelTaskType

if TYPE_CHECKING:
    from vnalpha.assistant.gateway import LLMGatewayClient

MISSING_DATA_TEMPLATES = {
    "no_candidate_score": "No candidate score found for {symbol} on {date}. Run `vnalpha score --date {date}` first.",
    "no_feature_snapshot": "No feature snapshot found for {symbol}. Run `vnalpha build features --date {date}` first.",
    "no_canonical_ohlcv": "No canonical OHLCV found for {symbol}. Run `vnalpha build canonical` first.",
    "no_watchlist": "No watchlist found for {date}. Run `vnalpha score --date {date}` first.",
    "generic": "Required data is not available. {detail}",
}

CONTEXT_INTENT_DISCLOSURES = {
    "review_market_regime": (
        "Describe the persisted market-regime snapshot, methodology, freshness, "
        "quality, lineage, and caveats."
    ),
    "review_sector_strength": (
        "Describe persisted sector ranking, methodology, freshness, coverage, "
        "lineage, and caveats."
    ),
    "review_symbol_sector_alignment": (
        "Describe only persisted symbol metadata and matching sector context; "
        "state missing metadata without inference."
    ),
}

CONTEXT_INTENTS = frozenset(CONTEXT_INTENT_DISCLOSURES)
UNSAFE_CONTEXT_TERMS = TRADING_EXECUTION_PHRASES | frozenset(
    {"rebalance", "position", "invest", "purchase", "allocate", "allocation", "margin"}
)

SYNTHESIZER_SYSTEM_PROMPT = """You are a research assistant for a Vietnamese stock market screening tool.

Your role is to explain deterministic tool outputs as persisted research context.

STRICT RULES:
1. Use only the provided tool outputs as factual data.
2. You MUST NOT override persisted scores, classes, setup types, quality, lineage, or methodology.
3. Do not give action guidance, personalized advice, or execution instructions.
4. Do not claim certainty or guaranteed future outcomes.
5. State missing, partial, stale, or unavailable evidence explicitly.
6. Include basis, freshness, methodology, quality, lineage, risks, caveats, and missing data when available.
7. When a research template is supplied, follow its required sections and caveats.
8. Shortlist and scenario outputs are research-prioritization artifacts requiring human review.

Respond only as JSON:
{
  "summary": "...",
  "basis": "...",
  "risks_caveats": "...",
  "tool_trace_summary": "...",
  "missing_data": []
}
"""


def _build_synthesis_messages(
    user_prompt: str, plan: AssistantPlan, tool_outputs: dict[str, Any]
) -> list[dict]:
    context = {
        "user_question": user_prompt,
        "intent": plan.intent,
        "required_artifacts": plan.required_artifacts,
        "context_intent_disclosure": CONTEXT_INTENT_DISCLOSURES.get(plan.intent),
        "research_template": research_template_prompt(plan.intent),
        "tool_outputs": tool_outputs,
    }
    return [
        {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(context, default=str, ensure_ascii=False),
        },
    ]


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


class AnswerSynthesizer:
    def __init__(self, llm_client: LLMGatewayClient):
        self._client = llm_client
        self.last_usage: dict | None = None
        self.last_groundedness: GroundednessResult | None = None

    def synthesize(
        self,
        user_prompt: str,
        plan: AssistantPlan,
        tool_outputs: dict[str, Any],
    ) -> AssistantAnswer:
        """Synthesize a grounded answer using task-aware model routing."""

        precheck = validate_tool_grounding(plan, tool_outputs)
        assert_grounded(precheck)
        messages = _build_synthesis_messages(user_prompt, plan, tool_outputs)
        task_type = task_type_for_plan(plan)
        symbol_count = _symbol_count(plan)
        context_bytes = len(messages[-1]["content"].encode("utf-8"))
        try:
            response_text, usage = self._client.chat(
                messages,
                stage="synthesize",
                task_type=task_type,
                route_metadata={
                    "symbol_count": symbol_count,
                    "artifact_count": len(tool_outputs),
                    "context_bytes": context_bytes,
                    "requires_deep_reasoning": task_type
                    in {
                        ModelTaskType.MULTI_SYMBOL_COMPARISON.value,
                        ModelTaskType.DEEP_SYMBOL_ANALYSIS.value,
                        ModelTaskType.SHORTLIST_GENERATION.value,
                        ModelTaskType.RESEARCH_SCENARIO.value,
                    },
                },
            )
        except Exception as exc:
            raise SynthesisError(f"LLM synthesis call failed: {exc}") from exc

        self.last_usage = usage
        answer = parse_synthesis_response(response_text)
        _validate_context_answer(plan, tool_outputs, answer)
        groundedness = validate_research_answer(plan, tool_outputs, answer)
        self.last_groundedness = groundedness
        assert_grounded(groundedness)
        return answer


def _validate_context_answer(
    plan: AssistantPlan, tool_outputs: dict[str, Any], answer: AssistantAnswer
) -> None:
    if plan.intent not in CONTEXT_INTENTS:
        return
    answer_text = " ".join(
        (answer.summary, answer.basis, answer.risks_caveats)
    ).lower()
    if any(term in answer_text for term in UNSAFE_CONTEXT_TERMS):
        raise SynthesisError("Context synthesis must remain research-only.")
    if _requires_caveat_first(tool_outputs) and not answer.summary.lower().startswith(
        "caveat"
    ):
        raise SynthesisError("Context synthesis must be caveat-first for limited data.")


def _requires_caveat_first(tool_outputs: dict[str, Any]) -> bool:
    for output in tool_outputs.values():
        if not isinstance(output, dict):
            continue
        data = output.get("data", output)
        if not isinstance(data, dict):
            continue
        quality = data.get("quality")
        if ("snapshot" in data and data["snapshot"] is None) or data.get("caveats"):
            return True
        if "snapshots" in data and not data["snapshots"]:
            return True
        if quality in {"INSUFFICIENT_DATA", "INCOMPLETE", "PARTIAL"}:
            return True
    return False
