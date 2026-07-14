"""Typed readiness artifacts and remediation for market and sector context."""

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
    remediation: RemediationStep,
    symbol_metadata: tuple[tuple[str, str], ...] = (),
) -> ReadinessArtifact:
    """Build one artifact whose blocking behavior follows its requirement."""
    blocking = requirement is ContextRequirement.REQUIRED
    failed = bool(issues)
    error = public_message(issues[0]) if failed and blocking else None
    return ReadinessArtifact(
        name=name,
        status=status(requirement, failed, actions),
        actions=actions,
        freshness=freshness,
        lineage=lineage,
        error=error,
        remediation=remediation.command if failed else None,
        available=not failed,
        requested_date=requested_date,
        resolved_date=requested_date,
        observed_as_of_date=observed_as_of_date,
        row_count=row_count,
        quality_status=quality_status,
        methodology_version=methodology_version,
        symbol_metadata=symbol_metadata,
        error_code=issues[0].value if failed else None,
        remediation_steps=(remediation,) if failed else (),
        requirement=requirement,
        required=blocking,
        blocking=blocking,
        issues=issues,
    )


def status(
    requirement: ContextRequirement, failed: bool, actions: tuple[str, ...]
) -> ReadinessArtifactStatus:
    """Determine artifact status without treating optional data as a hard gate."""
    if failed:
        return (
            ReadinessArtifactStatus.FAILED
            if requirement is ContextRequirement.REQUIRED
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
        case unreachable:
            assert_never(unreachable)


def market_remediation(target_date: date) -> RemediationStep:
    """Return the exact-date legacy command for market context."""
    return RemediationStep(
        action=RemediationAction.BUILD_MARKET_REGIME,
        artifact="market_regime_snapshot",
        command_surface="cli",
        command=f"vnalpha build market-regime --date {target_date.isoformat()}",
        description="Build exact-date market regime from persisted inputs.",
        required=True,
    )


def sector_remediation(target_date: date) -> RemediationStep:
    """Return the exact-date legacy command for sector context."""
    return RemediationStep(
        action=RemediationAction.BUILD_SECTOR_STRENGTH,
        artifact="sector_strength_snapshot",
        command_surface="cli",
        command=f"vnalpha build sector-strength --date {target_date.isoformat()}",
        description="Build exact-date sector strength from persisted inputs.",
        required=True,
    )
