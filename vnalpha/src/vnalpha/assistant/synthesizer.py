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
from vnalpha.assistant.policy import TRADING_EXECUTION_PHRASES
from vnalpha.assistant.response_parser import parse_synthesis_response

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
UNSAFE_CONTEXT_TERMS = TRADING_EXECUTION_PHRASES | frozenset(
    {"rebalance", "position", "invest", "purchase", "allocate", "allocation", "margin"}
)

SYNTHESIZER_SYSTEM_PROMPT = """You are a research assistant for a Vietnamese stock market screening tool.

Your role is to explain deterministic pipeline outputs to the user as persisted research context.

STRICT RULES:
1. You MUST use only the provided tool outputs as your data source.
2. You MUST NOT override the score, candidate_class, setup_type, or quality_status from tool outputs.
3. You MUST NOT give action guidance or recommendations.
4. You MUST NOT claim certainty or make guaranteed predictions.
5. If data is missing or None in tool outputs, state it clearly; do not invent values.
6. Always include methodology, freshness, lineage, quality or coverage, caveats, basis, and missing data.
7. When caveats, missing data, stale data, partial coverage, or insufficient quality exist,
   the summary MUST state those limitations before descriptive conclusions.
8. Market and sector context is descriptive persisted research context, not a forecast.

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
        "required_artifacts": plan.required_artifacts,
        "context_intent_disclosure": CONTEXT_INTENT_DISCLOSURES.get(plan.intent),
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
        messages = _build_synthesis_messages(user_prompt, plan, tool_outputs)
        try:
            response_text, usage = self._client.chat(messages, stage="synthesize")
        except Exception as exc:
            raise SynthesisError(f"LLM synthesis call failed: {exc}") from exc
        self.last_usage = usage
        answer = parse_synthesis_response(response_text)
        _validate_context_answer(plan, tool_outputs, answer)
        return answer


def _validate_context_answer(
    plan: AssistantPlan, tool_outputs: dict[str, Any], answer: AssistantAnswer
) -> None:
    if plan.intent not in CONTEXT_INTENTS:
        return
    answer_text = " ".join((answer.summary, answer.basis, answer.risks_caveats)).lower()
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
