"""Validation utilities for research automation artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal, Mapping

from vnalpha.research_automation.models import (
    ArtifactOutputs,
    ResearchArtifact,
    ResearchArtifactType,
)

_RECOMMENDATION_PATTERNS: Final[tuple[str, ...]] = (
    r"\b(i|we)\s+(recommend|suggest)\b",
    r"\bshould\s+(buy|sell|go\s+long|go\s+short)\b",
    r"\bbuy\s+now\b",
    r"\bsell\s+now\b",
    r"\btake\s+profit\b",
    r"\bplace\s+order\b",
)
_RECOMMENDATION_RE = tuple(
    re.compile(item, re.IGNORECASE) for item in _RECOMMENDATION_PATTERNS
)

_EXPERIMENT_METRICS: Final[tuple[str, str]] = ("sample_size", "period_coverage")


@dataclass(frozen=True, slots=True)
class ResearchArtifactValidationFinding:
    severity: Literal["error", "warning"]
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class ResearchArtifactValidationReport:
    findings: tuple[ResearchArtifactValidationFinding, ...] = field(
        default_factory=tuple
    )

    @property
    def is_ok(self) -> bool:
        return all(item.severity != "error" for item in self.findings)


def validate_research_artifact(
    *,
    outputs: ArtifactOutputs,
    artifact: ResearchArtifact | None = None,
) -> ResearchArtifactValidationReport:
    """Validate mandatory artifacts and high-level research safety constraints."""

    findings: list[ResearchArtifactValidationFinding] = []

    result_payload = _require_json(findings, "result", outputs.result_json)
    lineage_payload = _require_json(findings, "lineage", outputs.lineage_json)
    validation_payload = _require_json(findings, "validation", outputs.validation_json)
    _ = _require_json(findings, "manifest", outputs.manifest)
    _require_text(findings, "summary", outputs.summary_md)
    _require_file(findings, "summary", outputs.summary_md)

    if artifact is None:
        _warn_if_missing_lineage_and_quality(findings, {}, None)
        _warn_if_missing_caveats(findings, ())
    else:
        _warn_if_missing_lineage_and_quality(
            findings, artifact.quality_status, artifact.lineage
        )
        _warn_if_missing_caveats(findings, artifact.caveats)
        _validate_sample_coverage(
            findings,
            artifact=artifact,
            result_payload=result_payload,
            lineage_payload=lineage_payload,
            validation_payload=validation_payload,
        )

    if not _contains_prohibited_recommendation(outputs.summary_md, findings):
        _ = None

    return ResearchArtifactValidationReport(findings=tuple(findings))


def generate_research_caveats(
    *,
    sample_size: int | None,
    period_coverage: float | None,
    quality_status: dict[str, Any] | None = None,
    lookahead_bias: bool = True,
    survivorship_bias: bool = True,
    transaction_costs_included: bool = False,
    research_only: bool = True,
) -> tuple[str, ...]:
    """Build reusable caveats used across experiment and pattern workflows."""

    caveats: list[str] = []

    if sample_size is None:
        caveats.append(
            "Sample size was not recorded; interpretation should be cautious."
        )
    elif sample_size < 30:
        caveats.append(
            f"Small sample size ({sample_size}) increases estimate variance."
        )

    if period_coverage is None:
        caveats.append("Period coverage was not recorded for this artifact.")
    elif period_coverage < 0.7:
        caveats.append(
            f"Period coverage is incomplete ({period_coverage:.0%}); coverage risk applies."
        )

    if quality_status is not None:
        status = quality_status.get("status")
        if status and str(status).lower() in {"bad", "warn", "warning", "low"}:
            caveats.append(f"Data quality status is {status!r}.")
        for issue in quality_status.get("warnings", ()):
            caveat = str(issue).strip()
            if caveat:
                caveats.append(caveat)

    if lookahead_bias:
        caveats.append(
            "Potential lookahead bias must be reviewed for data timing and feature construction."
        )
    if survivorship_bias:
        caveats.append(
            "Survivorship bias is possible if inactive symbols were removed from source snapshots."
        )
    if not transaction_costs_included:
        caveats.append("Transaction costs are excluded from these computed metrics.")
    if research_only:
        caveats.append(
            "This is research-only output, not personalized financial guidance."
        )

    return tuple(dict.fromkeys(c for c in caveats if c))


def _require_file(
    findings: list[ResearchArtifactValidationFinding], label: str, path: Path
) -> None:
    if not path.exists():
        findings.append(
            ResearchArtifactValidationFinding(
                severity="error",
                code="missing_file",
                message=f"Missing required {label} artifact: {path}",
                path=str(path),
            )
        )


def _require_text(
    findings: list[ResearchArtifactValidationFinding],
    label: str,
    path: Path,
) -> str | None:
    _require_file(findings, label, path)
    if not path.exists():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        findings.append(
            ResearchArtifactValidationFinding(
                severity="error",
                code="invalid_text",
                message=f"Unable to read {label} artifact as UTF-8 text: {exc}",
                path=str(path),
            )
        )
        return None
    if not value:
        findings.append(
            ResearchArtifactValidationFinding(
                severity="error",
                code="empty_text",
                message=f"Summary artifact is empty: {path}",
                path=str(path),
            )
        )
    return value


def _require_json(
    findings: list[ResearchArtifactValidationFinding],
    label: str,
    path: Path,
) -> dict[str, Any] | None:
    _require_file(findings, label, path)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(
            ResearchArtifactValidationFinding(
                severity="error",
                code="unreadable_json",
                message=f"Unable to read {label} json artifact: {exc}",
                path=str(path),
            )
        )
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        findings.append(
            ResearchArtifactValidationFinding(
                severity="error",
                code="invalid_json",
                message=f"Malformed {label} json artifact: {exc}",
                path=str(path),
            )
        )
        return None
    if not isinstance(payload, dict):
        findings.append(
            ResearchArtifactValidationFinding(
                severity="error",
                code="json_shape",
                message=f"{label} artifact payload is not a JSON object: {path}",
                path=str(path),
            )
        )
        return None
    return payload


def _warn_if_missing_lineage_and_quality(
    findings: list[ResearchArtifactValidationFinding],
    quality_status: Mapping[str, Any],
    lineage: Mapping[str, Any] | None,
) -> None:
    if not quality_status:
        findings.append(
            ResearchArtifactValidationFinding(
                severity="warning",
                code="missing_quality_status",
                message="Quality status was not attached to the artifact.",
            )
        )
    if not lineage:
        findings.append(
            ResearchArtifactValidationFinding(
                severity="warning",
                code="missing_lineage",
                message="Lineage was not attached to the artifact.",
            )
        )


def _warn_if_missing_caveats(
    findings: list[ResearchArtifactValidationFinding],
    caveats: tuple[str, ...],
) -> None:
    if not caveats:
        findings.append(
            ResearchArtifactValidationFinding(
                severity="warning",
                code="missing_caveats",
                message="Artifact caveats were not attached.",
            )
        )


def _validate_sample_coverage(
    findings: list[ResearchArtifactValidationFinding],
    artifact: ResearchArtifact,
    result_payload: dict[str, Any] | None,
    lineage_payload: dict[str, Any] | None,
    validation_payload: dict[str, Any] | None,
) -> None:
    if artifact.artifact_type in {
        ResearchArtifactType.INDICATOR_EXPERIMENT,
        ResearchArtifactType.HYPOTHESIS_TEST,
    }:
        source = artifact.metrics or {}
        if result_payload is not None:
            source = {**source, **result_payload}
        if validation_payload is not None:
            source = {**source, **validation_payload}
        if lineage_payload is not None:
            source = {**source, **lineage_payload}

        for metric in _EXPERIMENT_METRICS:
            value = source.get(metric)
            if value is None:
                findings.append(
                    ResearchArtifactValidationFinding(
                        severity="warning",
                        code=f"missing_experiment_metric:{metric}",
                        message=f"Missing required experiment metric {metric!r} for {artifact.artifact_type.value}.",
                    )
                )


def _contains_prohibited_recommendation(
    summary_path: Path,
    findings: list[ResearchArtifactValidationFinding],
) -> bool:
    try:
        text = summary_path.read_text(encoding="utf-8").lower()
    except (OSError, UnicodeDecodeError):
        return True
    for pattern in _RECOMMENDATION_RE:
        if pattern.search(text) is not None:
            findings.append(
                ResearchArtifactValidationFinding(
                    severity="error",
                    code="personalized_recommendation",
                    message="Final artifact contains recommendation-like language.",
                    path=str(summary_path),
                )
            )
            return True
    return False
