"""Typed readiness artifacts and root-cause remediation for market/sector context."""

from __future__ import annotations

from datetime import date
from typing import assert_never

from vnalpha.data_availability.deep_readiness_models import (
    ContextIssue,
    ContextRequirement,
    ReadinessArtifact,
    ReadinessArtifactStatus,
    RemediationAction,
    RemediationStep,
)

Evidence = tuple[tuple[str, object], ...]


def not_requested(
    name: str, requirement: ContextRequirement, requested_date: str
) -> ReadinessArtifact:
    """Describe a context artifact intentionally excluded from the request."""
    return ReadinessArtifact(
        name=name,
        status=ReadinessArtifactStatus.NOT_REQUESTED,
        actions=(),
        freshness="not_requested",
        lineage=(),
        error=None,
        remediation=None,
        requested_date=requested_date,
        resolved_date=requested_date,
        requirement=requirement,
        required=False,
        blocking=False,
    )


def invalid_requirement(name: str, requested_date: str) -> ReadinessArtifact:
    """Return a blocking typed result without touching persisted context."""
    return context_artifact(
        name=name,
        requirement=ContextRequirement.INVALID,
        requested_date=requested_date,
        issues=(ContextIssue.INVALID_CONTEXT_REQUIREMENT,),
        actions=(),
        freshness="invalid_request",
        observed_as_of_date=None,
        row_count=0,
        quality_status="invalid_request",
        methodology_version=None,
        lineage=(),
        remediation_steps=(),
    )


def context_artifact(
    *,
    name: str,
    requirement: ContextRequirement,
    requested_date: str,
    issues: tuple[ContextIssue, ...],
    actions: tuple[str, ...],
    freshness: str,
    observed_as_of_date: str | None,
    row_count: int,
    quality_status: str,
    methodology_version: str | None,
    lineage: tuple[str, ...],
    remediation_steps: tuple[RemediationStep, ...],
    symbol_metadata: tuple[tuple[str, str], ...] = (),
    evidence: Evidence = (),
    generated_at: str | None = None,
    benchmark_as_of_date: str | None = None,
) -> ReadinessArtifact:
    """Build one artifact whose blocking behavior follows its requirement."""
    blocking = requirement in {
        ContextRequirement.REQUIRED,
        ContextRequirement.INVALID,
    }
    failed = bool(issues)
    error = public_message(issues[0]) if failed and blocking else None
    return ReadinessArtifact(
        name=name,
        status=status(requirement, failed, actions),
        actions=actions,
        freshness=freshness,
        lineage=lineage,
        error=error,
        remediation=remediation_steps[0].command
        if failed and remediation_steps
        else None,
        available=not failed,
        requested_date=requested_date,
        resolved_date=requested_date,
        observed_as_of_date=observed_as_of_date,
        row_count=row_count,
        quality_status=quality_status,
        lineage_status="complete" if lineage else "unknown",
        generated_at=generated_at,
        methodology_version=methodology_version,
        benchmark_as_of_date=benchmark_as_of_date,
        symbol_metadata=symbol_metadata,
        error_code=issues[0].value if failed else None,
        remediation_steps=remediation_steps if failed else (),
        requirement=requirement,
        required=blocking,
        blocking=blocking,
        issues=issues,
        breadth_active_count=_evidence_int(evidence, "breadth_active_count"),
        breadth_eligible_count=_evidence_int(evidence, "breadth_eligible_count"),
        breadth_excluded_count=_evidence_int(evidence, "breadth_excluded_count"),
        breadth_coverage=_evidence_float(evidence, "breadth_coverage"),
        ranked_sector_count=_evidence_int(evidence, "ranked_sector_count"),
        member_count=_evidence_int(evidence, "member_count"),
        eligible_count=_evidence_int(evidence, "eligible_count"),
        excluded_count=_evidence_int(evidence, "excluded_count"),
        metadata_coverage=_evidence_float(evidence, "metadata_coverage"),
        classified_count=_evidence_int(evidence, "classified_count"),
        unclassified_count=_evidence_int(evidence, "unclassified_count"),
        rank=_evidence_int(evidence, "rank"),
        score=_evidence_float(evidence, "score"),
        rotation=_evidence_text(evidence, "rotation"),
    )


def _evidence_text(evidence: Evidence, key: str) -> str | None:
    value = dict(evidence).get(key)
    if value is None:
        return None
    text = str(value).strip()
    return None if text.casefold() in {"", "none", "null", "nan"} else text


def _evidence_int(evidence: Evidence, key: str) -> int | None:
    value = _evidence_text(evidence, key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _evidence_float(evidence: Evidence, key: str) -> float | None:
    value = _evidence_text(evidence, key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def status(
    requirement: ContextRequirement, failed: bool, actions: tuple[str, ...]
) -> ReadinessArtifactStatus:
    """Determine artifact status without treating optional data as a hard gate."""
    if failed:
        return (
            ReadinessArtifactStatus.FAILED
            if requirement in {ContextRequirement.REQUIRED, ContextRequirement.INVALID}
            else ReadinessArtifactStatus.PARTIAL
        )
    return (
        ReadinessArtifactStatus.PROVISIONED
        if actions
        else ReadinessArtifactStatus.READY
    )


def public_message(issue: ContextIssue) -> str:
    """Return the allowlisted public message for a typed context issue."""
    match issue:
        case ContextIssue.MARKET_REGIME_MISSING:
            return "Required market regime context is unavailable."
        case ContextIssue.MARKET_REGIME_STALE:
            return "Required market regime context is stale."
        case ContextIssue.MARKET_REGIME_INPUT_COVERAGE_INSUFFICIENT:
            return "Market regime inputs do not have sufficient persisted coverage."
        case ContextIssue.MARKET_REGIME_QUALITY_UNACCEPTABLE:
            return "Market regime context does not meet the required quality policy."
        case ContextIssue.SECTOR_STRENGTH_MISSING:
            return "Required sector strength context is unavailable."
        case ContextIssue.SECTOR_STRENGTH_STALE:
            return "Required sector strength context is stale."
        case ContextIssue.SECTOR_INPUT_COVERAGE_INSUFFICIENT:
            return "Sector strength inputs do not have sufficient persisted coverage."
        case ContextIssue.SECTOR_METADATA_INSUFFICIENT:
            return (
                "Sector classification metadata is insufficient for required context."
            )
        case ContextIssue.SYMBOL_SECTOR_UNCLASSIFIED:
            return "The symbol has no usable persisted sector classification."
        case ContextIssue.SECTOR_NOT_RANKABLE:
            return "The symbol sector is not rankable in the persisted snapshot."
        case ContextIssue.CONTEXT_BUILD_FAILED:
            return "Required context could not be built from persisted inputs."
        case ContextIssue.INVALID_CONTEXT_REQUIREMENT:
            return "The requested context requirement is invalid."
        case unreachable:
            assert_never(unreachable)


def market_remediation_steps(
    target_date: date, issues: tuple[ContextIssue, ...]
) -> tuple[RemediationStep, ...]:
    """Map typed market issues to ordered commands that address the root cause."""
    if not issues or ContextIssue.INVALID_CONTEXT_REQUIREMENT in issues:
        return ()
    steps: list[RemediationStep] = []
    if ContextIssue.MARKET_REGIME_INPUT_COVERAGE_INSUFFICIENT in issues:
        steps.append(_build_features_step("market_regime_snapshot", target_date))
    steps.append(_build_market_step("market_regime_snapshot", target_date))
    return tuple(steps)


def sector_remediation_steps(
    target_date: date,
    issues: tuple[ContextIssue, ...],
    *,
    artifact: str = "sector_strength_snapshot",
) -> tuple[RemediationStep, ...]:
    """Map typed sector/alignment issues to ordered prerequisite repair commands."""
    if not issues or ContextIssue.INVALID_CONTEXT_REQUIREMENT in issues:
        return ()
    steps: list[RemediationStep] = []
    if any(
        issue
        in {
            ContextIssue.SECTOR_METADATA_INSUFFICIENT,
            ContextIssue.SYMBOL_SECTOR_UNCLASSIFIED,
        }
        for issue in issues
    ):
        steps.append(_sync_symbols_step(artifact))
    if any(
        issue
        in {
            ContextIssue.SECTOR_INPUT_COVERAGE_INSUFFICIENT,
            ContextIssue.SECTOR_NOT_RANKABLE,
        }
        for issue in issues
    ):
        steps.append(_build_features_step(artifact, target_date))
    steps.append(_build_sector_step(artifact, target_date))
    return tuple(steps)


def _sync_symbols_step(artifact: str) -> RemediationStep:
    return RemediationStep(
        action=RemediationAction.SYNC_SYMBOLS,
        artifact=artifact,
        command_surface="cli",
        command="vnalpha sync symbols",
        description="Refresh persisted symbol and sector metadata.",
        required=True,
    )


def _build_features_step(artifact: str, target_date: date) -> RemediationStep:
    return RemediationStep(
        action=RemediationAction.BUILD_FEATURES,
        artifact=artifact,
        command_surface="cli",
        command=f"vnalpha build features --date {target_date.isoformat()}",
        description="Rebuild exact-date persisted feature coverage for the market universe.",
        required=True,
    )


def _build_market_step(artifact: str, target_date: date) -> RemediationStep:
    return RemediationStep(
        action=RemediationAction.BUILD_MARKET_REGIME,
        artifact=artifact,
        command_surface="cli",
        command=f"vnalpha build market-regime --date {target_date.isoformat()}",
        description="Build exact-date market regime from persisted inputs.",
        required=True,
    )


def _build_sector_step(artifact: str, target_date: date) -> RemediationStep:
    return RemediationStep(
        action=RemediationAction.BUILD_SECTOR_STRENGTH,
        artifact=artifact,
        command_surface="cli",
        command=f"vnalpha build sector-strength --date {target_date.isoformat()}",
        description="Build exact-date sector strength from persisted inputs.",
        required=True,
    )
