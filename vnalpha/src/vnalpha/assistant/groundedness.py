from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.assistant.research_templates import (
    STRICT_POLICY_INTENTS,
    get_research_template,
)
from vnalpha.policy.research_language import validate_research_language


@dataclass(frozen=True, slots=True)
class GroundednessResult:
    status: str
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    tools_used: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    dataset_freshness: dict[str, Any] = field(default_factory=dict)
    policy_status: str = "PASS"

    @property
    def passed(self) -> bool:
        return self.status != "FAIL" and self.policy_status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_METRIC_KEYS: dict[str, tuple[str, ...]] = {
    "score": ("score", "shortlist_score"),
    "rank": ("rank", "research_rank"),
    "regime": ("regime",),
    "sector": ("sector", "sector_clusters"),
    "support": ("support_20d", "support_60d", "levels"),
    "resistance": ("resistance_20d", "resistance_60d", "levels"),
    "hit rate": ("hit_rate", "positive_outcome_rate"),
    "sample size": ("sample_size", "candidate_count"),
    "median return": ("median_forward_return",),
    "relative strength": (
        "relative_strength_score",
        "rs_20d_vs_vnindex",
        "rs_60d_vs_vnindex",
    ),
    "volatility": ("volatility_20d", "volatility", "atr14"),
}


def validate_tool_grounding(
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
) -> GroundednessResult:
    """Validate required deterministic tool payloads before synthesis."""

    template = get_research_template(plan.intent)
    if template is None:
        return GroundednessResult(status="PASS")
    if not plan.steps:
        return GroundednessResult(
            status="WARN",
            warnings=(
                "Direct synthesis call has no executable plan steps; "
                "tool-name validation was skipped.",
            ),
        )

    by_tool = _outputs_by_tool(plan, tool_outputs)
    issues: list[str] = []
    warnings: list[str] = []
    for tool_name in template.required_tools:
        if tool_name not in by_tool:
            issues.append(f"Required tool output is missing: {tool_name}.")

    primary_output = (
        by_tool.get(template.required_tools[0]) if template.required_tools else None
    )
    primary_data = _data_payload(primary_output)
    if template.required_data_keys and not isinstance(primary_data, dict):
        issues.append("Primary research tool did not return a structured data payload.")
    elif isinstance(primary_data, dict):
        for key in template.required_data_keys:
            if key not in primary_data:
                issues.append(f"Primary research payload is missing required key: {key}.")

    for output in by_tool.values():
        if not isinstance(output, dict):
            warnings.append("A tool output was not a structured mapping.")
            continue
        output_warnings = output.get("warnings")
        if isinstance(output_warnings, list):
            warnings.extend(str(item) for item in output_warnings if item)

    return GroundednessResult(
        status="FAIL" if issues else "WARN" if warnings else "PASS",
        issues=tuple(_dedupe(issues)),
        warnings=tuple(_dedupe(warnings)),
        tools_used=tuple(by_tool),
        artifact_refs=tuple(_collect_values(by_tool, "artifact_refs")),
        dataset_freshness=_collect_freshness(by_tool),
    )


def validate_research_answer(
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
    answer: AssistantAnswer,
) -> GroundednessResult:
    """Validate a synthesized answer against deterministic tool payloads."""

    precheck = validate_tool_grounding(plan, tool_outputs)
    template = get_research_template(plan.intent)
    if template is None:
        return precheck

    issues = list(precheck.issues)
    warnings = list(precheck.warnings)
    answer_text = " ".join(
        (answer.summary, answer.basis, answer.risks_caveats, answer.tool_trace_summary)
    ).strip()

    language = validate_research_language(
        answer_text,
        require_marker=plan.intent in STRICT_POLICY_INTENTS
        or template.require_research_marker,
    )
    if not language.passed:
        if language.forbidden_terms:
            issues.append("Answer contains execution-oriented wording.")
        else:
            issues.append("Answer is missing explicit research framing.")

    if not answer.risks_caveats.strip():
        issues.append("Research answer must include risks and caveats.")

    if _has_limited_or_missing_data(tool_outputs) and not answer.missing_data:
        issues.append(
            "Tool payload reports limited or missing data but answer does not disclose it."
        )

    payload_keys = _collect_keys(tool_outputs)
    lowered_answer = answer_text.lower()
    for label, accepted_keys in _METRIC_KEYS.items():
        if label in lowered_answer and not any(
            key in payload_keys for key in accepted_keys
        ):
            issues.append(
                f"Answer references '{label}' without a grounded payload field."
            )

    if precheck.status == "WARN" and not issues:
        warnings.append("Answer is grounded but upstream tool caveats remain.")

    status = "FAIL" if issues else "WARN" if warnings else "PASS"
    return GroundednessResult(
        status=status,
        issues=tuple(_dedupe(issues)),
        warnings=tuple(_dedupe(warnings)),
        tools_used=precheck.tools_used,
        artifact_refs=precheck.artifact_refs,
        dataset_freshness=precheck.dataset_freshness,
        policy_status=language.status,
    )


def assert_grounded(result: GroundednessResult) -> None:
    if result.passed:
        return
    detail = "; ".join(result.issues) or "research answer policy failed"
    raise SynthesisError(f"Research answer groundedness validation failed: {detail}")


def _outputs_by_tool(plan: AssistantPlan, tool_outputs: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for step in plan.steps:
        if step.step_id in tool_outputs:
            result[step.tool_name] = tool_outputs[step.step_id]
    return result


def _data_payload(output: Any) -> Any:
    if isinstance(output, dict) and "data" in output:
        return output.get("data")
    return output


def _has_limited_or_missing_data(value: Any) -> bool:
    """Return true for actual missing/partial payloads, not caveats alone."""

    if isinstance(value, dict):
        if value.get("data", object()) is None:
            return True
        status = str(value.get("status", "")).upper()
        if status in {"PARTIAL", "UNAVAILABLE", "MISSING", "INSUFFICIENT_DATA"}:
            return True
        missing = value.get("missing_data")
        if isinstance(missing, list) and bool(missing):
            return True
        return any(_has_limited_or_missing_data(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_limited_or_missing_data(item) for item in value)
    return False


def _collect_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for item in value.values():
            keys.update(_collect_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.update(_collect_keys(item))
    return keys


def _collect_values(value: Any, key_name: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == key_name:
                if isinstance(item, (list, tuple)):
                    found.extend(str(entry) for entry in item if entry)
                elif item:
                    found.append(str(item))
            else:
                found.extend(_collect_values(item, key_name))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_collect_values(item, key_name))
    return _dedupe(found)


def _collect_freshness(value: Any) -> dict[str, Any]:
    freshness: dict[str, Any] = {}

    def walk(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                next_path = f"{path}.{key}" if path else str(key)
                if key in {
                    "freshness",
                    "as_of_date",
                    "as_of_bar_date",
                    "benchmark_as_of_bar_date",
                    "generated_at",
                }:
                    freshness[next_path] = nested
                else:
                    walk(nested, next_path)
        elif isinstance(item, (list, tuple)):
            for index, nested in enumerate(item[:20]):
                walk(nested, f"{path}[{index}]")

    walk(value, "")
    return freshness


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


__all__ = [
    "GroundednessResult",
    "assert_grounded",
    "validate_research_answer",
    "validate_tool_grounding",
]
