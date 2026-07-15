"""Ground final assistant responses in deterministic tool outputs."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.groundedness import (
    GroundednessResult,
    GroundednessValidator,
    available_source_refs,
)
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, AssistantRequest
from vnalpha.assistant.policy import (
    TRADING_EXECUTION_PHRASES,
    ResearchPolicyResult,
    validate_research_answer_policy,
)
from vnalpha.assistant.research_templates import (
    build_deterministic_research_answer,
    is_research_intent,
    research_prompt_fragment,
)
from vnalpha.assistant.response_parser import parse_synthesis_response
from vnalpha.model_routing.models import ModelTaskType

if TYPE_CHECKING:
    from vnalpha.assistant.gateway import LLMGatewayClient

MISSING_DATA_TEMPLATES = {
    "no_candidate_score": (
        "No candidate score found for {symbol} on {date}. "
        "Run `vnalpha score --date {date}` first."
    ),
    "no_feature_snapshot": (
        "No feature snapshot found for {symbol}. "
        "Run `vnalpha build features --date {date}` first."
    ),
    "no_canonical_ohlcv": (
        "No canonical OHLCV found for {symbol}. Run `vnalpha build canonical` first."
    ),
    "no_watchlist": (
        "No watchlist found for {date}. Run `vnalpha score --date {date}` first."
    ),
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
        "grounded_source_refs": {
            "type": "array",
            "items": {"type": "string"},
        },
        # Dynamic claim identifiers are intentionally disabled in strict mode.
        # Groundedness remains enforced through the bounded source-reference list.
        "claim_source_refs": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
        # Runtime validation metadata is added deterministically after the model call.
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
    messages = [
        {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
    ]
    if request is not None:
        from vnalpha.assistant.context import build_context_message

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


class AnswerSynthesizer:
    def __init__(self, llm_client: LLMGatewayClient):
        self._client = llm_client
        self.last_usage: dict | None = None
        self.last_raw_responses: list[dict[str, Any]] = []
        self.last_groundedness: GroundednessResult | None = None
        self.last_policy: ResearchPolicyResult | None = None
        self.last_fallback_used = False

    def synthesize(
        self,
        user_prompt: str,
        plan: AssistantPlan,
        tool_outputs: dict[str, Any],
        *,
        request: AssistantRequest | None = None,
        session_id: str | None = None,
    ) -> AssistantAnswer:
        """Synthesize and validate a grounded, policy-safe answer."""

        self.last_usage = None
        self.last_raw_responses = []
        self.last_groundedness = None
        self.last_policy = None
        self.last_fallback_used = False
        research_intent = is_research_intent(plan.intent)
        validator = GroundednessValidator()

        if research_intent and plan.steps:
            input_result = validator.validate_inputs(plan, tool_outputs)
            if not input_result.can_synthesize:
                detail = "; ".join(input_result.messages) or "invalid research inputs"
                raise SynthesisError(
                    f"Research tool payload validation failed before synthesis: {detail}"
                )

        messages = _build_synthesis_messages(
            user_prompt, plan, tool_outputs, request=request
        )
        task_type = task_type_for_plan(plan)
        symbol_count = _symbol_count(plan)
        context_bytes = len(messages[-1]["content"].encode("utf-8"))

        route_metadata = {
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
        }
        if session_id is not None:
            route_metadata["session_id"] = session_id

        try:
            response_text, usage = self._client.chat(
                messages,
                response_schema=SYNTHESIS_RESPONSE_SCHEMA,
                stage="synthesize",
                task_type=task_type,
                route_metadata=route_metadata,
            )
            self._capture_gateway_raw_responses()
            self.last_usage = usage
            answer = parse_synthesis_response(response_text)
        except Exception as exc:
            if not self.last_raw_responses:
                self._capture_gateway_raw_responses()
            if not research_intent:
                if isinstance(exc, SynthesisError):
                    raise
                raise SynthesisError(f"LLM synthesis call failed: {exc}") from exc
            return self._deterministic_fallback(
                plan,
                tool_outputs,
                validator,
                reasons=[f"Model synthesis was unavailable: {type(exc).__name__}."],
            )

        try:
            _validate_context_answer(plan, tool_outputs, answer)
        except SynthesisError:
            if plan.intent in CONTEXT_INTENTS:
                raise
            return self._deterministic_fallback(
                plan,
                tool_outputs,
                validator,
                reasons=["The model answer violated the research-language contract."],
            )

        if not research_intent:
            return answer

        groundedness = validator.validate(answer, plan, tool_outputs)
        policy = validate_research_answer_policy(answer, plan.intent)
        if groundedness.passed and policy.passed:
            return self._record_validation(
                answer,
                groundedness,
                policy,
                fallback_used=False,
            )

        reasons = list(groundedness.messages)
        if policy.violations:
            reasons.append(
                "The model answer failed research-language policy validation."
            )
        return self._deterministic_fallback(
            plan,
            tool_outputs,
            validator,
            reasons=reasons,
        )

    def _deterministic_fallback(
        self,
        plan: AssistantPlan,
        tool_outputs: dict[str, Any],
        validator: GroundednessValidator,
        *,
        reasons: list[str],
    ) -> AssistantAnswer:
        answer = build_deterministic_research_answer(
            plan,
            tool_outputs,
            reasons=list(dict.fromkeys(reason for reason in reasons if reason)),
        )
        groundedness = validator.validate(answer, plan, tool_outputs)
        policy = validate_research_answer_policy(answer, plan.intent)
        if not groundedness.passed or not policy.passed:
            detail = (
                "; ".join([*groundedness.messages, *policy.violations])
                or "deterministic fallback validation failed"
            )
            raise SynthesisError(
                f"Research answer failed closed after deterministic fallback: {detail}"
            )
        return self._record_validation(
            answer,
            groundedness,
            policy,
            fallback_used=True,
        )

    def _record_validation(
        self,
        answer: AssistantAnswer,
        groundedness: GroundednessResult,
        policy: ResearchPolicyResult,
        *,
        fallback_used: bool,
    ) -> AssistantAnswer:
        self.last_groundedness = groundedness
        self.last_policy = policy
        self.last_fallback_used = fallback_used
        answer.research_metadata = {
            **answer.research_metadata,
            "groundedness": groundedness.to_dict(),
            "policy": policy.to_dict(),
            "fallback_used": fallback_used,
        }
        return answer

    def _capture_gateway_raw_responses(self) -> None:
        raw_responses = getattr(self._client, "last_raw_responses", ())
        self.last_raw_responses = [dict(response) for response in raw_responses]


def _validate_context_answer(
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
    answer: AssistantAnswer,
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
