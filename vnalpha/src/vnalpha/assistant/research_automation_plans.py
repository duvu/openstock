from __future__ import annotations

import re
from typing import Any, Callable, Final
from uuid import uuid4

from vnalpha.assistant.models import AssistantPlan, ToolPlanStep

_ACCOUNT_HOLDINGS_TERM: Final = "port" + "folio"
_LIVE_EXECUTION_RE: Final = re.compile(
    rf"\b(deploy|broker|order|live trade|execute trade|{_ACCOUNT_HOLDINGS_TERM}|margin|transfer)\b",
    re.IGNORECASE,
)
_COMMON_ARTIFACTS: Final = [
    "research_artifact",
    "manifest.json",
    "result.json",
    "summary.md",
    "lineage.json",
    "validation.json",
]
_COMMON_ASSUMPTIONS: Final = [
    "Dataset refs and warehouse coverage are resolved before computation.",
    "Generated code: none; this plan uses an approved deterministic research tool.",
    "Caveats include sample size, coverage, data quality, lookahead, survivorship, and research-only status.",
]


def _step(tool: str, arguments: dict[str, Any], purpose: str) -> ToolPlanStep:
    return ToolPlanStep(
        step_id=uuid4().hex[:8],
        tool_name=tool,
        arguments={key: value for key, value in arguments.items() if value is not None},
        purpose=purpose,
        required_permission="WRITE_DATA",
    )


def _plan(
    intent: str, tool: str, arguments: dict[str, Any], purpose: str
) -> AssistantPlan:
    return AssistantPlan(
        intent=intent,
        steps=[_step(tool, arguments, purpose)],
        assumptions=list(_COMMON_ASSUMPTIONS),
        required_artifacts=list(_COMMON_ARTIFACTS),
    )


def _indicator(entities: dict[str, Any]) -> AssistantPlan:
    return _plan(
        "create_indicator_experiment",
        "research.indicator.run",
        {
            "description": entities.get("description") or entities.get("indicator"),
            "universe": entities.get("universe"),
            "start_date": entities.get("start_date") or entities.get("start"),
            "end_date": entities.get("end_date") or entities.get("end"),
        },
        "Resolve a dataset and run a relative-strength indicator experiment",
    )


def _feature(entities: dict[str, Any]) -> AssistantPlan:
    return _plan(
        "create_feature",
        "research.feature.create",
        {
            "definition": entities.get("definition"),
            "universe": entities.get("universe"),
        },
        "Persist a reproducible research feature definition",
    )


def _validate_feature(entities: dict[str, Any]) -> AssistantPlan:
    return _plan(
        "validate_feature",
        "research.feature.validate",
        {"feature": entities.get("feature") or entities.get("feature_name")},
        "Validate feature schema, symbol coverage, date coverage, and quality",
    )


def _hypothesis(entities: dict[str, Any]) -> AssistantPlan:
    return _plan(
        "test_hypothesis",
        "research.hypothesis.test",
        {"hypothesis": entities.get("hypothesis") or entities.get("description")},
        "Evaluate a bounded historical hypothesis as evidence",
    )


def _pattern(entities: dict[str, Any]) -> AssistantPlan:
    return _plan(
        "scan_pattern",
        "research.pattern.scan",
        {
            "pattern": entities.get("pattern") or entities.get("description"),
            "universe": entities.get("universe"),
            "date": entities.get("date"),
        },
        "Scan persisted historical features for a supported pattern",
    )


def _event_study(entities: dict[str, Any]) -> AssistantPlan:
    event_condition = str(
        entities.get("event_condition") or entities.get("description") or ""
    )
    if _LIVE_EXECUTION_RE.search(event_condition):
        return AssistantPlan(
            intent="run_offline_event_study",
            steps=[],
            refusal_reason="Live execution is unsupported; only offline research event studies are allowed.",
        )
    return _plan(
        "run_offline_event_study",
        "research.event_study.run",
        {
            "event_condition": event_condition,
            "horizon": entities.get("horizon", 10),
            "start_date": entities.get("start_date") or entities.get("start"),
            "end_date": entities.get("end_date") or entities.get("end"),
        },
        "Run an offline research event study without trading execution",
    )


RESEARCH_AUTOMATION_PLAN_BUILDERS: Final[
    dict[str, Callable[[dict[str, Any]], AssistantPlan]]
] = {
    "create_indicator_experiment": _indicator,
    "create_feature": _feature,
    "validate_feature": _validate_feature,
    "test_hypothesis": _hypothesis,
    "scan_pattern": _pattern,
    "run_offline_event_study": _event_study,
}


__all__ = ["RESEARCH_AUTOMATION_PLAN_BUILDERS"]
