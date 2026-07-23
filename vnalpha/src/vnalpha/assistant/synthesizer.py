"""Ground final assistant responses in deterministic tool outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnalpha.assistant.degraded_answer import (
    AssistantDegradation,
    AssistantFailureStage,
    build_deterministic_tool_answer,
)
from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.groundedness import (
    GroundednessResult,
    GroundednessValidator,
)
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, AssistantRequest
from vnalpha.assistant.policy import (
    ResearchPolicyResult,
    validate_research_answer_policy,
)
from vnalpha.assistant.research_templates import (
    build_deterministic_research_answer,
    is_research_intent,
)
from vnalpha.assistant.response_parser import parse_synthesis_response
from vnalpha.assistant.synthesis_prompt import (
    CONTEXT_INTENTS,
    SYNTHESIS_RESPONSE_SCHEMA,
    UNSAFE_CONTEXT_TERMS,
    _build_synthesis_messages,
    _symbol_count,
    task_type_for_plan,
)
from vnalpha.model_routing.models import ModelTaskType

if TYPE_CHECKING:
    from vnalpha.assistant.gateway import LLMGatewayClient


class AnswerSynthesizer:
    def __init__(self, llm_client: LLMGatewayClient):
        self._client = llm_client
        self.last_usage: dict | None = None
        self.last_raw_responses: list[dict[str, Any]] = []
        self.last_groundedness: GroundednessResult | None = None
        self.last_policy: ResearchPolicyResult | None = None
        self.last_fallback_used = False
        self.last_degradation: AssistantDegradation | None = None

    def synthesize(
        self,
        user_prompt: str,
        plan: AssistantPlan,
        tool_outputs: dict[str, Any],
        *,
        request: AssistantRequest | None = None,
        session_id: str | None = None,
    ) -> AssistantAnswer:
        self.last_usage = None
        self.last_raw_responses = []
        self.last_groundedness = None
        self.last_policy = None
        self.last_fallback_used = False
        self.last_degradation = None
        research_intent = is_research_intent(plan.intent)
        validator = GroundednessValidator()

        if research_intent and plan.steps:
            input_result = validator.validate_inputs(plan, tool_outputs)
            if not input_result.can_synthesize:
                detail = "; ".join(input_result.messages) or "invalid research inputs"
                return self._deterministic_fallback(
                    plan,
                    tool_outputs,
                    validator,
                    reasons=[detail],
                    degradation=AssistantDegradation(
                        AssistantFailureStage.ANSWER_VALIDATION,
                        "INPUT_VALIDATION",
                    ),
                )
            if _requires_deterministic_missing_answer(plan, tool_outputs):
                answer = build_deterministic_research_answer(plan, tool_outputs)
                groundedness = validator.validate(answer, plan, tool_outputs)
                policy = validate_research_answer_policy(answer, plan.intent)
                if groundedness.passed and policy.passed:
                    return self._record_validation(
                        answer,
                        groundedness,
                        policy,
                        fallback_used=False,
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
        except Exception as exc:
            if not self.last_raw_responses:
                self._capture_gateway_raw_responses()
            return self._deterministic_fallback(
                plan,
                tool_outputs,
                validator,
                reasons=[f"Model synthesis was unavailable: {type(exc).__name__}."],
                degradation=AssistantDegradation(
                    AssistantFailureStage.SYNTHESIS_CALL,
                    "GATEWAY_FAILURE",
                ),
            )
        try:
            answer = parse_synthesis_response(response_text)
        except SynthesisError:
            return self._deterministic_fallback(
                plan,
                tool_outputs,
                validator,
                reasons=["Model synthesis returned an invalid structured answer."],
                degradation=AssistantDegradation(
                    AssistantFailureStage.SYNTHESIS_PARSE,
                    "STRUCTURED_OUTPUT_INVALID",
                ),
            )

        try:
            _validate_context_answer(plan, tool_outputs, answer)
        except SynthesisError:
            return self._deterministic_fallback(
                plan,
                tool_outputs,
                validator,
                reasons=["The model answer violated the research-language contract."],
                degradation=AssistantDegradation(
                    AssistantFailureStage.ANSWER_VALIDATION,
                    "CONTEXT_POLICY_REJECTED",
                ),
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
            degradation=AssistantDegradation(
                AssistantFailureStage.ANSWER_VALIDATION,
                "GROUNDEDNESS_OR_POLICY_REJECTED",
            ),
        )

    def _deterministic_fallback(
        self,
        plan: AssistantPlan,
        tool_outputs: dict[str, Any],
        validator: GroundednessValidator,
        *,
        reasons: list[str],
        degradation: AssistantDegradation,
    ) -> AssistantAnswer:
        answer = build_deterministic_tool_answer(
            plan,
            tool_outputs,
            degradation,
            reasons=list(dict.fromkeys(reason for reason in reasons if reason)),
        )
        if answer is None:
            raise SynthesisError("No safe deterministic answer is available.")
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
        self.last_degradation = degradation
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


def _requires_deterministic_missing_answer(
    plan: AssistantPlan, tool_outputs: dict[str, Any]
) -> bool:
    if plan.intent in CONTEXT_INTENTS:
        for output in tool_outputs.values():
            data = output.get("data", output) if isinstance(output, dict) else None
            if isinstance(data, dict) and data.get("snapshot") is None:
                return True
    for step in plan.steps:
        output = tool_outputs.get(step.step_id)
        data = output.get("data", output) if isinstance(output, dict) else None
        if isinstance(data, dict) and data.get("status") in {
            "ACCEPTED",
            "PENDING",
            "UNAVAILABLE",
            "FAILED",
        }:
            return True
    return False
