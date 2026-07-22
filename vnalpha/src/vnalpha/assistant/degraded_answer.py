from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from os import environ
from typing import Any, Final

from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.assistant.research_templates import (
    build_deterministic_research_answer,
    is_research_intent,
)
from vnalpha.observability.context import get_correlation_id
from vnalpha.tools.setup import TOOL_PERMISSIONS

_PUBLIC_WARNING: Final = "AI synthesis unavailable; showing deterministic result."


class AssistantFailureStage(StrEnum):
    CLASSIFY = "CLASSIFY"
    PLAN = "PLAN"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    SYNTHESIS_CALL = "SYNTHESIS_CALL"
    SYNTHESIS_PARSE = "SYNTHESIS_PARSE"
    SYNTHESIS_PERSIST = "SYNTHESIS_PERSIST"
    ANSWER_VALIDATION = "ANSWER_VALIDATION"
    AUDIT_PERSIST = "AUDIT_PERSIST"
    KNOWLEDGE_PROJECTION = "KNOWLEDGE_PROJECTION"
    SESSION_FINALIZE = "SESSION_FINALIZE"


@dataclass(frozen=True, slots=True)
class AssistantDegradation:
    stage: AssistantFailureStage
    category: str
    warning: str = _PUBLIC_WARNING
    correlation_id: str | None = None
    trace_id: str | None = None
    model_route: str | None = None
    build_sha: str | None = None

    def to_dict(self) -> dict[str, str]:
        values = {
            "stage": self.stage.value,
            "category": self.category,
            "warning": self.warning,
            "correlation_id": self.correlation_id or get_correlation_id(),
            "trace_id": self.trace_id or "",
            "model_route": self.model_route or "",
            "build_sha": self.build_sha
            or environ.get("VNALPHA_BUILD_SHA")
            or environ.get("GITHUB_SHA")
            or "unknown",
        }
        return {key: value for key, value in values.items() if value}


def build_deterministic_tool_answer(
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
    degradation: AssistantDegradation,
    *,
    reasons: list[str] | None = None,
) -> AssistantAnswer | None:
    if not tool_outputs or not _is_read_only_plan(plan):
        return None
    summaries, warnings, source_refs = _tool_result_details(plan, tool_outputs)
    fallback_reasons = [degradation.warning, *(reasons or []), *warnings]
    if is_research_intent(plan.intent):
        answer = build_deterministic_research_answer(
            plan,
            tool_outputs,
            reasons=list(
                dict.fromkeys(reason for reason in fallback_reasons if reason)
            ),
        )
        if summaries:
            answer = replace(
                answer,
                basis=answer.basis + "; Tool result: " + summaries[0],
                grounded_source_refs=list(
                    dict.fromkeys([*answer.grounded_source_refs, *source_refs])
                ),
            )
    else:
        answer = AssistantAnswer(
            summary=summaries[0] if summaries else _data_summary(plan, tool_outputs),
            basis="Deterministic tools: "
            + ", ".join(step.tool_name for step in plan.steps),
            risks_caveats=" ".join(
                dict.fromkeys(reason for reason in fallback_reasons if reason)
            ),
            tool_trace_summary=(
                f"Executed {len(plan.steps)} deterministic tool(s): "
                + ", ".join(step.tool_name for step in plan.steps)
            ),
            grounded_source_refs=source_refs,
        )
    return replace(
        answer,
        research_metadata={
            **answer.research_metadata,
            "synthesis_status": "FALLBACK_SUCCESS",
            "fallback_reason": degradation.category,
            "llm_used": False,
            "degradation": degradation.to_dict(),
        },
    )


def with_degradation(
    answer: AssistantAnswer, degradation: AssistantDegradation
) -> AssistantAnswer:
    diagnostic = degradation.to_dict()
    previous = answer.research_metadata.get("degradations", [])
    degradations = (
        [*previous, diagnostic] if isinstance(previous, list) else [diagnostic]
    )
    return replace(
        answer,
        research_metadata={
            **answer.research_metadata,
            "synthesis_status": "DEGRADED_SUCCESS",
            "degradation": diagnostic,
            "degradations": degradations,
        },
    )


def degradation_warning(answer: AssistantAnswer) -> str | None:
    diagnostic = answer.research_metadata.get("degradation")
    if not isinstance(diagnostic, dict):
        return None
    warning = diagnostic.get("warning")
    stage = diagnostic.get("stage")
    category = diagnostic.get("category")
    correlation_id = diagnostic.get("correlation_id")
    if not all(
        isinstance(value, str) and value for value in (warning, stage, category)
    ):
        return None
    suffix = f" stage={stage} category={category}"
    if isinstance(correlation_id, str) and correlation_id:
        suffix += f" correlation_id={correlation_id}"
    return warning + suffix


def _is_read_only_plan(plan: AssistantPlan) -> bool:
    return all(
        TOOL_PERMISSIONS[step.tool_name].value.startswith("READ_")
        for step in plan.steps
    )


def _tool_result_details(
    plan: AssistantPlan, tool_outputs: dict[str, Any]
) -> tuple[list[str], list[str], list[str]]:
    summaries: list[str] = []
    warnings: list[str] = []
    source_refs = [f"tool:{step.tool_name}:{step.step_id}" for step in plan.steps]
    for step in plan.steps:
        output = tool_outputs.get(step.step_id)
        if not isinstance(output, dict):
            continue
        summary = output.get("summary")
        if isinstance(summary, str) and summary:
            summaries.append(summary)
        raw_warnings = output.get("warnings", [])
        if isinstance(raw_warnings, list):
            warnings.extend(
                warning
                for warning in raw_warnings
                if isinstance(warning, str) and warning
            )
        data = output.get("data")
        if isinstance(data, dict):
            refs = data.get("artifact_refs", [])
            if isinstance(refs, list):
                source_refs.extend(ref for ref in refs if isinstance(ref, str) and ref)
    return (
        list(dict.fromkeys(summaries)),
        list(dict.fromkeys(warnings)),
        list(dict.fromkeys(source_refs)),
    )


def _data_summary(plan: AssistantPlan, tool_outputs: dict[str, Any]) -> str:
    for step in plan.steps:
        output = tool_outputs.get(step.step_id)
        data = output.get("data") if isinstance(output, dict) else None
        if isinstance(data, dict):
            values = [
                f"{key}={value}"
                for key, value in data.items()
                if isinstance(value, (bool, int, float, str))
            ]
            if values:
                return "Deterministic result: " + ", ".join(values[:6]) + "."
    return "Deterministic tool result is available."
