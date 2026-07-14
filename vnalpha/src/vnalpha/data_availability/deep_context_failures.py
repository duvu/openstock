"""Sanitized outcomes for unavailable context storage."""

from __future__ import annotations

from datetime import date

from vnalpha.data_availability.deep_context_artifacts import (
    context_artifact,
    market_remediation,
    not_requested,
    sector_remediation,
)
from vnalpha.data_availability.deep_context_readiness import ContextReadinessInput
from vnalpha.data_availability.deep_readiness_models import (
    ContextIssue,
    ContextRequirement,
    ReadinessArtifact,
    RemediationStep,
)


def unavailable_context_artifacts(
    context: ContextReadinessInput, issue: ContextIssue
) -> tuple[ReadinessArtifact, ...]:
    """Return sanitized context outcomes when the warehouse cannot be queried."""
    target_date = date.fromisoformat(context.resolved_date)
    market = _unavailable(
        "market_regime_snapshot",
        context.market_regime_requirement,
        context.resolved_date,
        issue,
        market_remediation(target_date),
    )
    sector = _unavailable(
        "sector_strength_snapshot",
        context.sector_strength_requirement,
        context.resolved_date,
        issue,
        sector_remediation(target_date),
    )
    return market, sector, not_requested(
        "symbol_sector_alignment",
        context.sector_strength_requirement,
        context.resolved_date,
    )


def _unavailable(
    name: str,
    requirement: ContextRequirement,
    requested_date: str,
    issue: ContextIssue,
    remediation: RemediationStep,
) -> ReadinessArtifact:
    if requirement is ContextRequirement.NOT_REQUESTED:
        return not_requested(name, requirement, requested_date)
    return context_artifact(
        name=name,
        requirement=requirement,
        requested_date=requested_date,
        issues=(issue,),
        actions=(),
        freshness="unavailable",
        observed_as_of_date=None,
        row_count=0,
        quality_status="unavailable",
        methodology_version=None,
        lineage=(),
        remediation=remediation,
    )
