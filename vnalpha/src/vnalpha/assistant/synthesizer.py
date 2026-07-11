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
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.assistant.response_parser import parse_synthesis_response
from vnalpha.research_intelligence.scenario_templates import (
    render_research_scenario_answer,
)

if TYPE_CHECKING:
    from vnalpha.assistant.gateway import LLMGatewayClient

# Missing data templates
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
7. For deep_analyze_symbol, describe observed trend, levels, setup quality, monitoring conditions, and invalidation criteria. Never convert these observations into execution advice.
8. For generate_research_scenario, retain the research scenario plan's current setup, key levels, conditions, all scenario branches, confidence, caveats, research-only disclaimer, and future-confirmation context. Never turn the scenario into execution advice.
9. For market and sector context intents, describe persisted state, breadth, rankings, rotation, freshness, lineage, and caveats. Never convert observations into allocation or rebalance advice.

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


class AnswerSynthesizer:
    def __init__(self, llm_client: "LLMGatewayClient"):
        self._client = llm_client
        self.last_usage: dict | None = None

    def synthesize(
        self,
        user_prompt: str,
        plan: AssistantPlan,
        tool_outputs: dict[str, Any],
    ) -> AssistantAnswer:
        """Synthesize a grounded answer from tool outputs."""
        if plan.intent == "generate_research_scenario":
            return self._render_research_scenario(tool_outputs)
        messages = _build_synthesis_messages(user_prompt, plan, tool_outputs)
        try:
            response_text, usage = self._client.chat(messages, stage="synthesize")
        except Exception as exc:
            raise SynthesisError(f"LLM synthesis call failed: {exc}") from exc
        self.last_usage = usage
        return parse_synthesis_response(response_text)

    def _render_research_scenario(
        self, tool_outputs: dict[str, Any]
    ) -> AssistantAnswer:
        scenario_plan = _scenario_plan_from_tool_outputs(tool_outputs)
        try:
            rendered = render_research_scenario_answer(
                scenario_plan, tool_outputs=tool_outputs
            )
        except Exception as exc:
            raise SynthesisError(f"Scenario rendering failed: {exc}") from exc
        self.last_usage = None
        return AssistantAnswer(**rendered)


def _scenario_plan_from_tool_outputs(
    tool_outputs: dict[str, Any],
) -> Mapping[str, Any]:
    for output in tool_outputs.values():
        if not isinstance(output, Mapping):
            continue
        data = output.get("data", output)
        if isinstance(data, Mapping) and "scenario_plan_id" in data:
            return data
    raise SynthesisError(
        "Scenario synthesis requires a persisted scenario plan output."
    )
