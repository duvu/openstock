"""Read-only availability snapshots and deterministic provisioning plans."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

import duckdb

from vnalpha.data_availability.cache import evaluate_cache_eligibility
from vnalpha.data_availability.checks import (
    compute_lookback_start,
    get_benchmark_status,
    get_candidate_score_artifact_evidence,
    get_candidate_score_evidence,
    get_canonical_ohlcv_status,
    get_feature_snapshot_evidence,
    get_feature_snapshot_status,
    get_latest_canonical_bar_date,
    get_ohlcv_evidence,
    get_symbol_master_evidence,
    get_symbol_master_status,
)
from vnalpha.data_availability.models import (
    ArtifactEvidence,
    DataArtifact,
    EnsureDataAction,
    EvidenceIssue,
    evidence_issue_artifact,
)
from vnalpha.data_availability.ohlcv_gap_checks import (
    UnresolvedTrueGapWindow,
    count_unresolved_true_gaps,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_availability.relative_strength_checks import (
    get_relative_strength_evidence,
)


@dataclass(frozen=True, slots=True)
class EnsureDataSnapshot:
    symbol: str
    target_date: str
    lookback_start: str
    symbol_known: bool
    canonical_bars: int
    benchmark_bars: int
    feature_snapshot_exists: bool
    candidate_score_exists: bool
    candidate_score_as_of_date: str | None = None
    quality_status: str | None = None
    lineage_fields: frozenset[str] = frozenset()
    artifact_evidence: tuple[ArtifactEvidence, ...] = ()
    unresolved_true_gap_count: int = 0
    latest_canonical_bar_date: str | None = None
    latest_benchmark_bar_date: str | None = None


@dataclass(frozen=True, slots=True)
class EnsureDataPlan:
    snapshot: EnsureDataSnapshot
    actions: tuple[EnsureDataAction, ...]


def capture_availability_snapshot(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
    policy: DataAvailabilityPolicy,
) -> EnsureDataSnapshot:
    """Capture all warehouse checks without triggering provisioning."""

    lookback_start = compute_lookback_start(target_date, policy.lookback_days)
    score_evidence = get_candidate_score_evidence(conn, symbol, target_date)
    feature_evidence = get_feature_snapshot_evidence(conn, symbol, target_date)
    relative_strength_evidence = get_relative_strength_evidence(
        conn, symbol, target_date
    )
    feature_evidence = replace(
        feature_evidence,
        available=feature_evidence.available and relative_strength_evidence.available,
        benchmark_as_of_date=(
            relative_strength_evidence.benchmark_bar_date
            or feature_evidence.benchmark_as_of_date
        ),
        benchmark_row_count=(
            relative_strength_evidence.benchmark_row_count
            or feature_evidence.benchmark_row_count
        ),
    )
    snapshot = EnsureDataSnapshot(
        symbol=symbol,
        target_date=target_date,
        lookback_start=lookback_start,
        symbol_known=get_symbol_master_status(conn, symbol),
        canonical_bars=get_canonical_ohlcv_status(
            conn, symbol, target_date, lookback_start
        ),
        benchmark_bars=get_benchmark_status(
            conn, policy.benchmark, target_date, lookback_start
        ),
        latest_canonical_bar_date=get_latest_canonical_bar_date(
            conn, symbol, target_date
        ),
        latest_benchmark_bar_date=get_latest_canonical_bar_date(
            conn, policy.benchmark, target_date
        ),
        feature_snapshot_exists=get_feature_snapshot_status(conn, symbol, target_date),
        candidate_score_exists=score_evidence.exists,
        candidate_score_as_of_date=score_evidence.as_of_bar_date,
        quality_status=score_evidence.quality_status,
        lineage_fields=score_evidence.lineage_fields,
        unresolved_true_gap_count=count_unresolved_true_gaps(
            conn,
            UnresolvedTrueGapWindow(
                symbol=symbol,
                lookback_start=lookback_start,
                target_date=target_date,
            ),
        ),
        artifact_evidence=(
            get_symbol_master_evidence(conn, symbol),
            get_ohlcv_evidence(
                conn,
                symbol,
                target_date,
                lookback_start,
                DataArtifact.CANONICAL_OHLCV,
            ),
            get_ohlcv_evidence(
                conn,
                policy.benchmark,
                target_date,
                lookback_start,
                DataArtifact.BENCHMARK_OHLCV,
            ),
            feature_evidence,
            get_candidate_score_artifact_evidence(conn, symbol, target_date),
        ),
    )
    eligibility = evaluate_cache_eligibility(snapshot, policy)
    return replace(
        snapshot,
        artifact_evidence=tuple(
            replace(
                evidence,
                required_row_count=(
                    policy.min_required_bars
                    if evidence.artifact
                    in {DataArtifact.CANONICAL_OHLCV, DataArtifact.BENCHMARK_OHLCV}
                    else evidence.required_row_count
                ),
                issues=tuple(
                    issue
                    for issue in eligibility.issues
                    if evidence_issue_artifact(issue) is evidence.artifact
                ),
                freshness=(
                    "stale"
                    if any(
                        issue is EvidenceIssue.SCORE_STALE
                        for issue in eligibility.issues
                        if evidence_issue_artifact(issue) is evidence.artifact
                    )
                    else evidence.freshness
                ),
            )
            for evidence in snapshot.artifact_evidence
        ),
    )


def plan_data_availability(
    snapshot: EnsureDataSnapshot, policy: DataAvailabilityPolicy
) -> EnsureDataPlan:
    """Return the ordered actions required by a read-only snapshot."""

    if evaluate_cache_eligibility(snapshot, policy).eligible:
        return EnsureDataPlan(snapshot=snapshot, actions=())

    actions: list[EnsureDataAction] = []
    if not snapshot.symbol_known and policy.auto_sync:
        actions.append(EnsureDataAction.SYMBOLS_SYNCED)

    canonical_missing = snapshot.canonical_bars < policy.min_required_bars
    canonical_stale = _canonical_is_stale(
        snapshot.latest_canonical_bar_date, snapshot.target_date
    )
    canonical_needs_sync = canonical_missing or canonical_stale
    canonical_will_be_built = canonical_needs_sync and policy.auto_sync
    if canonical_will_be_built:
        actions.extend(
            (EnsureDataAction.OHLCV_SYNCED, EnsureDataAction.CANONICAL_BUILT)
        )

    benchmark_missing = (
        policy.require_benchmark_history
        and snapshot.benchmark_bars < policy.min_required_bars
    )
    benchmark_stale = (
        policy.require_benchmark_history
        and snapshot.benchmark_bars >= policy.min_required_bars
        and _canonical_is_stale(
            snapshot.latest_benchmark_bar_date, snapshot.target_date
        )
    )
    if (benchmark_missing or benchmark_stale) and policy.auto_sync:
        actions.extend(
            (
                EnsureDataAction.BENCHMARK_SYNCED,
                EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
            )
        )

    feature_can_be_built = (
        snapshot.canonical_bars >= policy.min_required_bars or canonical_will_be_built
    )
    # A stale canonical refresh yields a newer bar date, so any existing feature
    # snapshot for target_date must be rebuilt rather than reused.
    feature_will_be_built = (
        policy.auto_sync
        and (not snapshot.feature_snapshot_exists or canonical_will_be_built)
        and feature_can_be_built
    )
    if feature_will_be_built:
        actions.append(EnsureDataAction.FEATURES_BUILT)

    if policy.auto_sync and (snapshot.feature_snapshot_exists or feature_will_be_built):
        actions.append(EnsureDataAction.SCORED)

    return EnsureDataPlan(snapshot=snapshot, actions=tuple(actions))


def _canonical_is_stale(
    latest_bar_date: str | None, target_date: str
) -> bool:
    """Return True when canonical history exists but predates *target_date*.

    Triggers a bounded incremental OHLCV sync when the caller requests analysis
    for a date newer than the latest ingested bar (data not yet caught up),
    rather than silently rebuilding features on a stale window. Returns False
    when no bars exist (that is handled by the history-insufficient path) or the
    dates cannot be parsed.
    """
    if latest_bar_date is None:
        return False
    try:
        latest = date.fromisoformat(latest_bar_date)
        target = date.fromisoformat(target_date)
    except ValueError:
        return False
    return latest < target
