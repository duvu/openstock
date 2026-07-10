"""
AnswerSynthesizer: grounds the final assistant response in tool outputs.

Rules:
- Tool outputs are the authoritative source of truth.
- The LLM must not override persisted score, candidate_class, setup_type, or quality_status.
- If a required artifact is missing from tool outputs, state it explicitly; do not fabricate.
- Every answer must include basis/evidence and risks/caveats.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
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

SYNTHESIZER_SYSTEM_PROMPT = """You are a research assistant for a Vietnamese stock market screening tool.

Your role is to explain deterministic pipeline outputs to the user.

STRICT RULES:
1. You MUST use only the provided tool outputs as your data source.
2. You MUST NOT override the score, candidate_class, setup_type, or quality_status from tool outputs.
3. You MUST NOT give buy/sell/order recommendations.
4. You MUST NOT claim certainty or make guaranteed predictions.
5. If data is missing or None in tool outputs, state it clearly; do not invent values.
6. Always include: basis (what tool returned), risks/caveats (from risk_flags and quality), and missing data.

Use research language only:
- "Based on the latest persisted score..."
- "The screening engine classifies this as..."
- "Main risk flags are..."
- "Data quality status is..."

Respond in JSON:
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
        "compare_symbols": ModelTaskType.MULTI_SYMBOL_COMPARISON.value,
        "deep_analyze_symbol": ModelTaskType.DEEP_SYMBOL_ANALYSIS.value,
        "generate_shortlist": ModelTaskType.SHORTLIST_GENERATION.value,
        "generate_research_scenario": ModelTaskType.RESEARCH_SCENARIO.value,
    }
    return mapping.get(plan.intent, ModelTaskType.NORMAL_ANSWER.value)


class AnswerSynthesizer:
    def __init__(self, llm_client: LLMGatewayClient):
        self._client = llm_client
        self.last_usage: dict | None = None

    def synthesize(
        self,
        user_prompt: str,
        plan: AssistantPlan,
        tool_outputs: dict[str, Any],
    ) -> AssistantAnswer:
        """Synthesize a grounded answer using task-aware model routing."""
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
        return parse_synthesis_response(response_text)
