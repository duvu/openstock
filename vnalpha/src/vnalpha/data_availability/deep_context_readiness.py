"""Bounded readiness evaluation for persisted market and sector context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb

from vnalpha.data_availability.deep_context_artifacts import (
    context_artifact,
    market_remediation,
    not_requested,
    sector_remediation,
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
    snapshot = get_market_regime_as_of(context.conn, target_date)
    issues = market_issues(
        snapshot, get_latest_market_regime(context.conn), target_date, False
    )
    action = ()
    if issues:
        action = _try_build_market(context.conn, target_date)
        snapshot = get_market_regime_as_of(context.conn, target_date)
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
        lineage=tuple(sorted(snapshot.lineage)) if snapshot else (),
        remediation=market_remediation(target_date),
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
    snapshots = get_sector_strength_as_of(context.conn, target_date)
    issues = sector_issues(
        snapshots, get_latest_sector_strength(context.conn), target_date, False
    )
    action = ()
    if issues:
        action = _try_build_sector(context.conn, target_date)
        snapshots = get_sector_strength_as_of(context.conn, target_date)
        issues = sector_issues(
            snapshots,
            get_latest_sector_strength(context.conn),
            target_date,
            _build_failed(action),
        )
    sector = context_artifact(
        name="sector_strength_snapshot",
        requirement=requirement,
        requested_date=context.resolved_date,
        issues=issues,
        actions=action,
        freshness="exact" if not issues else freshness(issues),
        observed_as_of_date=context.resolved_date if snapshots else None,
        row_count=len(snapshots),
        quality_status=snapshots[0].quality if snapshots else "missing",
        methodology_version=snapshots[0].methodology_version if snapshots else None,
        lineage=tuple(sorted(snapshots[0].lineage)) if snapshots else (),
        remediation=sector_remediation(target_date),
    )
    alignment = get_symbol_sector_alignment(context.conn, context.symbol, target_date)
    alignment_issue_list = alignment_issues(alignment, _build_failed(action))
    symbol_metadata = ()
    if alignment is not None and alignment.sector is not None:
        symbol_metadata = (("sector", alignment.sector),)
    return sector, context_artifact(
        name="symbol_sector_alignment",
        requirement=requirement,
        requested_date=context.resolved_date,
        issues=alignment_issue_list,
        actions=action,
        freshness="exact"
        if not alignment_issue_list
        else freshness(alignment_issue_list),
        observed_as_of_date=context.resolved_date
        if alignment is not None and alignment.snapshot is not None
        else None,
        row_count=1 if alignment is not None and alignment.snapshot is not None else 0,
        quality_status=(
            alignment.snapshot.quality
            if alignment is not None and alignment.snapshot is not None
            else "missing"
        ),
        methodology_version=(
            alignment.snapshot.methodology_version
            if alignment is not None and alignment.snapshot is not None
            else None
        ),
        lineage=(
            tuple(sorted(alignment.snapshot.lineage))
            if alignment is not None and alignment.snapshot is not None
            else ()
        ),
        remediation=sector_remediation(target_date),
        symbol_metadata=symbol_metadata,
    )


def _try_build_market(
    conn: duckdb.DuckDBPyConnection, target_date: date
) -> tuple[str, ...]:
    try:
        build_market_regime(conn, target_date)
    except Exception:  # noqa: BROAD_EXCEPT_OK
        return (ContextIssue.CONTEXT_BUILD_FAILED.value,)
    return (RemediationAction.BUILD_MARKET_REGIME.value,)


def _try_build_sector(
    conn: duckdb.DuckDBPyConnection, target_date: date
) -> tuple[str, ...]:
    try:
        build_sector_strength(conn, target_date)
    except Exception:  # noqa: BROAD_EXCEPT_OK
        return (ContextIssue.CONTEXT_BUILD_FAILED.value,)
    return (RemediationAction.BUILD_SECTOR_STRENGTH.value,)


def _build_failed(actions: tuple[str, ...]) -> bool:
    return "CONTEXT_BUILD_FAILED" in actions
