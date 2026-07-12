from __future__ import annotations

import re
from enum import Enum

from vnalpha.closed_loop.models import PromotableArtifactType
from vnalpha.policy.safety_policy import FORBIDDEN_TOOL_PREFIXES

_NON_RESEARCH_PREFIXES = frozenset({"network", "python", "mcp", "sql", "filesystem"})
_RESEARCH_BOUNDARY_PREFIXES = FORBIDDEN_TOOL_PREFIXES.difference(_NON_RESEARCH_PREFIXES)
_LIVE_PATTERN = re.compile(r"\blive[_ -]?(?:order|execution|trade)\b")
_EXECUTION_CALL_PATTERN = re.compile(r"\b(?:buy|sell|trade|short|cover)\s*\(")

_ARTIFACT_TYPE_ALIASES: dict[str, PromotableArtifactType] = {
    "indicator_experiment": PromotableArtifactType.INDICATOR_DEFINITION,
    "indicator_definition": PromotableArtifactType.INDICATOR_DEFINITION,
    "feature": PromotableArtifactType.FEATURE_DEFINITION,
    "feature_definition": PromotableArtifactType.FEATURE_DEFINITION,
    "experiment_template": PromotableArtifactType.EXPERIMENT_TEMPLATE,
    "hypothesis_test": PromotableArtifactType.EXPERIMENT_TEMPLATE,
    "pattern_scan": PromotableArtifactType.PATTERN_SCANNER_DEFINITION,
    "pattern_scanner_definition": PromotableArtifactType.PATTERN_SCANNER_DEFINITION,
    "offline_event_study": PromotableArtifactType.OFFLINE_EVENT_STUDY_TEMPLATE,
    "offline_event_study_template": PromotableArtifactType.OFFLINE_EVENT_STUDY_TEMPLATE,
}


def prohibited_behaviors(value: str) -> tuple[str, ...]:
    lowered = value.lower()
    findings = [
        prefix
        for prefix in sorted(_RESEARCH_BOUNDARY_PREFIXES)
        if re.search(rf"(?<![a-z]){re.escape(prefix)}(?![a-z])", lowered)
    ]
    if _LIVE_PATTERN.search(lowered) is not None and "trading" not in findings:
        findings.append("trading")
    if (
        _EXECUTION_CALL_PATTERN.search(lowered) is not None
        and "trading" not in findings
    ):
        findings.append("trading")
    return tuple(findings)


def parse_artifact_type(value: str) -> PromotableArtifactType:
    try:
        return PromotableArtifactType(value)
    except ValueError:
        try:
            return _ARTIFACT_TYPE_ALIASES[value]
        except KeyError as exc:
            raise ValueError(f"unsupported research artifact type: {value}") from exc


def allowed_proposal_text(
    patch: str, replacement_code: str
) -> tuple[bool, tuple[str, ...]]:
    findings = prohibited_behaviors(f"{patch}\n{replacement_code}")
    return not findings, findings


def is_research_artifact_type(value: str | Enum) -> bool:
    try:
        parse_artifact_type(value.value if isinstance(value, Enum) else value)
    except ValueError:
        return False
    return True
