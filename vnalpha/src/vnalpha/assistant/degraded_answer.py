from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from os import environ
from pathlib import Path
from re import fullmatch
from subprocess import DEVNULL, check_output
from typing import Any, Final

from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.assistant.research_templates import (
    build_deterministic_research_answer,
    is_research_intent,
)
from vnalpha.maintenance.software_identity import resolve_software_identity
from vnalpha.observability.context import get_correlation_id
from vnalpha.tools.setup import TOOL_PERMISSIONS

_PUBLIC_WARNING: Final = "AI synthesis unavailable; showing deterministic result."
_LIFECYCLE_WARNING: Final = "Assistant request did not produce a usable answer."
_LIFECYCLE_CAUSE: Final = "LIFECYCLE_FAILURE"
_PUBLIC_FALLBACK_LIMITATION: Final = (
    "Deterministic fallback is limited to available tool evidence."
)
_PUBLIC_TOOL_WARNING: Final = "Tool output reported a caveat."
_PUBLIC_WARNINGS: Final = frozenset({_PUBLIC_WARNING, _LIFECYCLE_WARNING})
_PUBLIC_MODEL_ROUTES: Final = frozenset(
    {"small", "default", "reasoning", "long_context", "client"}
)
_PUBLIC_CATEGORIES: Final = frozenset(
    {
        "AUDIT_PERSIST_FAILURE",
        "CLASSIFICATION_FAILURE",
        "CLASSIFY_TRACE_PERSIST_FAILURE",
        "PREPARE_PERSIST_FAILURE",
        "CONTEXT_POLICY_REJECTED",
        "GATEWAY_FAILURE",
        "GROUNDEDNESS_OR_POLICY_REJECTED",
        "KNOWLEDGE_PROJECTION_FAILURE",
        "INPUT_VALIDATION",
        "PLAN_BUILD_FAILURE",
        "SYNTHESIS_FAIL_CLOSED",
        "SYNTHESIS_PARSE_FAILURE",
        "SYNTHESIS_TRACE_CREATE_FAILURE",
        "SYNTHESIS_TRACE_PERSIST_FAILURE",
        "SESSION_FINALIZE_FAILURE",
        "SESSION_CREATE_FAILURE",
        "STRUCTURED_OUTPUT_INVALID",
        "TOOL_EXECUTION_FAILURE",
        "TOOL_TRACE_CREATE_FAILURE",
    }
)


class AssistantFailureStage(StrEnum):
    CLASSIFY = "CLASSIFY"
    PLAN = "PLAN"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    SYNTHESIS_CALL = "SYNTHESIS_CALL"
    SYNTHESIS_PARSE = "SYNTHESIS_PARSE"
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
            "category": (
                self.category if self.category in _PUBLIC_CATEGORIES else "UNSPECIFIED"
            ),
            "warning": (
                self.warning if self.warning in _PUBLIC_WARNINGS else _PUBLIC_WARNING
            ),
            "correlation_id": _public_identifier(
                "correlation_id", self.correlation_id or get_correlation_id()
            ),
            "trace_id": _public_identifier("trace_id", self.trace_id),
            "model_route": _public_identifier("model_route", self.model_route),
            "build_sha": _public_identifier(
                "build_sha", self.build_sha or _runtime_build_sha()
            ),
        }
        return {key: value for key, value in values.items() if value}


def build_deterministic_tool_answer(
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
    degradation: AssistantDegradation,
    *,
    reasons: list[str] | None = None,
) -> AssistantAnswer | None:
    if (
        not tool_outputs
        or not _is_read_only_plan(plan)
        or any(
            not isinstance(tool_outputs.get(step.step_id), dict)
            or not tool_outputs[step.step_id]
            for step in plan.steps
        )
    ):
        return None
    summaries, warnings, source_refs = _tool_result_details(plan, tool_outputs)
    fallback_reasons = [_public_fallback_reasons(degradation, reasons, warnings)]
    if is_research_intent(plan.intent):
        answer = build_deterministic_research_answer(
            plan,
            tool_outputs,
            reasons=list(fallback_reasons),
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
            risks_caveats=" ".join(fallback_reasons),
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
            "fallback_reason": degradation.to_dict()["category"],
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
    return diagnostic_warning(diagnostic)


def lifecycle_warning(
    stage: AssistantFailureStage,
    category: str,
    correlation_id: str | None,
    *,
    trace_id: str | None = None,
    model_route: str | None = None,
) -> str:
    return (
        diagnostic_warning(
            {
                "warning": _LIFECYCLE_WARNING,
                "cause": _LIFECYCLE_CAUSE,
                "stage": stage.value,
                "category": category,
                "correlation_id": correlation_id or get_correlation_id(),
                "trace_id": trace_id or "",
                "model_route": model_route or "",
                "build_sha": _runtime_build_sha() or "unavailable",
            }
        )
        or "Assistant request did not produce a usable answer."
    )


def diagnostic_warning(diagnostic: dict[str, Any]) -> str | None:
    warning = diagnostic.get("warning")
    stage = diagnostic.get("stage")
    category = diagnostic.get("category")
    if (
        warning not in _PUBLIC_WARNINGS
        or category not in _PUBLIC_CATEGORIES
        or not isinstance(stage, str)
    ):
        return None
    try:
        public_stage = AssistantFailureStage(stage)
    except ValueError:
        return None
    suffix = f" stage={public_stage.value} category={category}"
    if warning == _LIFECYCLE_WARNING and diagnostic.get("cause") == _LIFECYCLE_CAUSE:
        suffix += f" cause={_LIFECYCLE_CAUSE}"
    for key in ("correlation_id", "trace_id", "model_route", "build_sha"):
        if value := _public_identifier(key, diagnostic.get(key)):
            suffix += f" {key}={value}"
    return warning + suffix


def _public_identifier(key: str, value: object) -> str:
    if not isinstance(value, str):
        return ""
    patterns = {
        "correlation_id": r"[0-9a-f]{16,64}",
        "trace_id": r"[0-9a-f-]{16,64}",
        "build_sha": r"[0-9a-f]{7,64}",
    }
    if key == "model_route":
        return value if value in _PUBLIC_MODEL_ROUTES else ""
    return value if fullmatch(patterns[key], value) else ""


def _public_fallback_reasons(
    degradation: AssistantDegradation,
    reasons: list[str] | None,
    warnings: list[str],
) -> str:
    values = [
        degradation.warning
        if degradation.warning in _PUBLIC_WARNINGS
        else _PUBLIC_WARNING
    ]
    if reasons:
        values.append(_PUBLIC_FALLBACK_LIMITATION)
    if warnings:
        values.append(_PUBLIC_TOOL_WARNING)
    return " ".join(dict.fromkeys(values))


def _is_read_only_plan(plan: AssistantPlan) -> bool:
    return (
        bool(plan.steps)
        and not plan.is_refusal()
        and plan.intent != "unsupported_or_unsafe"
        and all(
            (permission := TOOL_PERMISSIONS.get(step.tool_name)) is not None
            and permission.value.startswith("READ_")
            for step in plan.steps
        )
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


def _runtime_build_sha() -> str | None:
    configured = environ.get("VNALPHA_BUILD_SHA") or environ.get("GITHUB_SHA")
    if configured:
        return _public_identifier("build_sha", configured) or None
    try:
        source_commit = resolve_software_identity().source_commit
        if source_commit:
            return _public_identifier("build_sha", source_commit) or None
        return (
            check_output(
                ["git", "-C", str(Path(__file__).parents[4]), "rev-parse", "HEAD"],
                stderr=DEVNULL,
                text=True,
                timeout=1,
            ).strip()
            or None
        )
    except Exception:
        return None
