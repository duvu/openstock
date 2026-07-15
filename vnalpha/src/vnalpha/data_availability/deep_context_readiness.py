"""Bounded readiness evaluation for persisted market and sector context."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

import duckdb

from vnalpha.data_availability.deep_context_artifacts import (
    context_artifact,
    invalid_requirement,
    market_remediation_steps,
    not_requested,
    sector_remediation_steps,
)
from vnalpha.data_availability.deep_context_evidence import (
    alignment_issues,
    freshness,
    market_issues,
    sector_issues,
)
from vnalpha.data_availability.deep_readiness_models import (
    ContextIssue,
    ContextRequirement,
    ReadinessArtifact,
    RemediationAction,
)
from vnalpha.research_intelligence.regime import build_market_regime
from vnalpha.research_intelligence.sector import build_sector_strength
from vnalpha.warehouse.repositories import (
    get_latest_market_regime,
    get_latest_sector_strength,
    get_market_regime_as_of,
    get_sector_strength_as_of,
    get_symbol_sector_alignment,
)


@dataclass(frozen=True, slots=True)
class ContextReadinessInput:
    """Typed context decision inputs after core readiness resolves its date."""

    conn: duckdb.DuckDBPyConnection
    symbol: str
    resolved_date: str
    market_regime_requirement: ContextRequirement
    sector_strength_requirement: ContextRequirement
    correlation_id: str = "unset"


def evaluate_context_readiness(
    context: ContextReadinessInput,
) -> tuple[ReadinessArtifact, ...]:
    """Evaluate and, when requested, rebuild only bounded persisted context."""
    target_date = date.fromisoformat(context.resolved_date)
    market = _market_artifact(context, target_date)
    sector, alignment = _sector_artifacts(context, target_date)
    return market, sector, alignment


def _market_artifact(
    context: ContextReadinessInput, target_date: date
) -> ReadinessArtifact:
    requirement = context.market_regime_requirement
    if requirement is ContextRequirement.NOT_REQUESTED:
        return not_requested(
            "market_regime_snapshot", requirement, context.resolved_date
        )
    if requirement is ContextRequirement.INVALID:
        return invalid_requirement("market_regime_snapshot", context.resolved_date)

    snapshot = get_market_regime_as_of(context.conn, target_date)
    issues = market_issues(
        snapshot, get_latest_market_regime(context.conn), target_date, False
    )
    action: tuple[str, ...] = ()
    if issues:
        action = _try_build_market(context, target_date)
        snapshot = get_market_regime_as_of(context.conn, target_date)
        from vnalpha.data_availability.deep_readiness_audit import audit_context_build

        audit_context_build("market_regime_snapshot", "REVALIDATED", context)
        issues = market_issues(
            snapshot,
            get_latest_market_regime(context.conn),
            target_date,
            _build_failed(action),
        )

    return context_artifact(
        name="market_regime_snapshot",
        requirement=requirement,
        requested_date=context.resolved_date,
        issues=issues,
        actions=action,
        freshness="exact" if not issues else freshness(issues),
        observed_as_of_date=snapshot.as_of_date.isoformat() if snapshot else None,
        row_count=1 if snapshot else 0,
        quality_status=snapshot.quality if snapshot else "missing",
        methodology_version=snapshot.methodology_version if snapshot else None,
        lineage=_lineage_keys(snapshot.lineage) if snapshot else (),
        remediation_steps=market_remediation_steps(target_date, issues),
        generated_at=_iso_timestamp(snapshot.generated_at) if snapshot else None,
        benchmark_as_of_date=(
            snapshot.benchmark_bar_date.isoformat() if snapshot else None
        ),
        evidence=(
            (
                "breadth_active_count",
                snapshot.breadth_active_count if snapshot else None,
            ),
            (
                "breadth_eligible_count",
                snapshot.breadth_eligible_count if snapshot else None,
            ),
            (
                "breadth_excluded_count",
                snapshot.breadth_excluded_count if snapshot else None,
            ),
            ("breadth_coverage", snapshot.breadth_coverage if snapshot else None),
        ),
    )


def _sector_artifacts(
    context: ContextReadinessInput, target_date: date
) -> tuple[ReadinessArtifact, ReadinessArtifact]:
    requirement = context.sector_strength_requirement
    if requirement is ContextRequirement.NOT_REQUESTED:
        return (
            not_requested(
                "sector_strength_snapshot", requirement, context.resolved_date
            ),
            not_requested(
                "symbol_sector_alignment", requirement, context.resolved_date
            ),
        )
    if requirement is ContextRequirement.INVALID:
        return (
            invalid_requirement("sector_strength_snapshot", context.resolved_date),
            invalid_requirement("symbol_sector_alignment", context.resolved_date),
        )

    snapshots = get_sector_strength_as_of(context.conn, target_date)
    issues = sector_issues(
        snapshots, get_latest_sector_strength(context.conn), target_date, False
    )
    action: tuple[str, ...] = ()
    if issues:
        action = _try_build_sector(context, target_date)
        snapshots = get_sector_strength_as_of(context.conn, target_date)
        from vnalpha.data_availability.deep_readiness_audit import audit_context_build

        audit_context_build("sector_strength_snapshot", "REVALIDATED", context)
        issues = sector_issues(
            snapshots,
            get_latest_sector_strength(context.conn),
            target_date,
            _build_failed(action),
        )

    first = snapshots[0] if snapshots else None
    sector = context_artifact(
        name="sector_strength_snapshot",
        requirement=requirement,
        requested_date=context.resolved_date,
        issues=issues,
        actions=action,
        freshness="exact" if not issues else freshness(issues),
        observed_as_of_date=context.resolved_date if first else None,
        row_count=len(snapshots),
        quality_status=first.quality if first else "missing",
        methodology_version=first.methodology_version if first else None,
        lineage=_lineage_keys(first.lineage) if first else (),
        remediation_steps=sector_remediation_steps(target_date, issues),
        generated_at=_iso_timestamp(first.generated_at) if first else None,
        evidence=(
            ("ranked_sector_count", len(snapshots)),
            ("member_count", first.member_count if first else None),
            ("eligible_count", first.eligible_count if first else None),
            (
                "excluded_count",
                max(first.member_count - first.eligible_count, 0) if first else None,
            ),
            ("metadata_coverage", first.metadata_coverage if first else None),
            ("classified_count", first.eligible_count if first else None),
            ("unclassified_count", first.unclassified_count if first else None),
            ("rank", first.rank if first else None),
            ("score", first.score if first else None),
            ("rotation", first.rotation if first else None),
        ),
    )

    alignment = get_symbol_sector_alignment(context.conn, context.symbol, target_date)
    alignment_issue_list = alignment_issues(alignment, _build_failed(action))
    alignment_snapshot = alignment.snapshot if alignment is not None else None
    symbol_metadata = (
        (("sector", alignment.sector),)
        if alignment is not None and alignment.sector is not None
        else ()
    )
    alignment_artifact = context_artifact(
        name="symbol_sector_alignment",
        requirement=requirement,
        requested_date=context.resolved_date,
        issues=alignment_issue_list,
        actions=action,
        freshness=(
            "exact" if not alignment_issue_list else freshness(alignment_issue_list)
        ),
        observed_as_of_date=(
            alignment_snapshot.as_of_date.isoformat() if alignment_snapshot else None
        ),
        row_count=1 if alignment_snapshot else 0,
        quality_status=alignment_snapshot.quality if alignment_snapshot else "missing",
        methodology_version=(
            alignment_snapshot.methodology_version if alignment_snapshot else None
        ),
        lineage=_lineage_keys(alignment_snapshot.lineage) if alignment_snapshot else (),
        remediation_steps=sector_remediation_steps(
            target_date,
            alignment_issue_list,
            artifact="symbol_sector_alignment",
        ),
        symbol_metadata=symbol_metadata,
        generated_at=(
            _iso_timestamp(alignment_snapshot.generated_at)
            if alignment_snapshot
            else None
        ),
        evidence=(
            (
                "member_count",
                alignment_snapshot.member_count if alignment_snapshot else None,
            ),
            (
                "eligible_count",
                alignment_snapshot.eligible_count if alignment_snapshot else None,
            ),
            (
                "excluded_count",
                max(
                    alignment_snapshot.member_count - alignment_snapshot.eligible_count,
                    0,
                )
                if alignment_snapshot
                else None,
            ),
            (
                "metadata_coverage",
                alignment_snapshot.metadata_coverage if alignment_snapshot else None,
            ),
            (
                "unclassified_count",
                alignment_snapshot.unclassified_count if alignment_snapshot else None,
            ),
            ("rank", alignment_snapshot.rank if alignment_snapshot else None),
            ("score", alignment_snapshot.score if alignment_snapshot else None),
            ("rotation", alignment_snapshot.rotation if alignment_snapshot else None),
        ),
    )
    return sector, alignment_artifact


def _try_build_market(
    context: ContextReadinessInput, target_date: date
) -> tuple[str, ...]:
    from vnalpha.data_availability.deep_readiness_audit import audit_context_build

    audit_context_build("market_regime_snapshot", "STARTED", context)
    try:
        build_market_regime(context.conn, target_date)
    except Exception:  # noqa: BROAD_EXCEPT_OK
        audit_context_build("market_regime_snapshot", "FAILED", context)
        return (ContextIssue.CONTEXT_BUILD_FAILED.value,)
    audit_context_build("market_regime_snapshot", "SUCCEEDED", context)
    return (RemediationAction.BUILD_MARKET_REGIME.value,)


def _try_build_sector(
    context: ContextReadinessInput, target_date: date
) -> tuple[str, ...]:
    from vnalpha.data_availability.deep_readiness_audit import audit_context_build

    audit_context_build("sector_strength_snapshot", "STARTED", context)
    try:
        build_sector_strength(context.conn, target_date)
    except Exception:  # noqa: BROAD_EXCEPT_OK
        audit_context_build("sector_strength_snapshot", "FAILED", context)
        return (ContextIssue.CONTEXT_BUILD_FAILED.value,)
    audit_context_build("sector_strength_snapshot", "SUCCEEDED", context)
    return (RemediationAction.BUILD_SECTOR_STRENGTH.value,)


def _build_failed(actions: tuple[str, ...]) -> bool:
    return ContextIssue.CONTEXT_BUILD_FAILED.value in actions


def _lineage_keys(lineage: Mapping[str, str] | None) -> tuple[str, ...]:
    return tuple(sorted(lineage)) if lineage else ()


def _iso_timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
