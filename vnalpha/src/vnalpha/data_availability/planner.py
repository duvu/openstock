"""Read-only availability snapshots and deterministic provisioning plans."""

from __future__ import annotations

from dataclasses import dataclass, replace

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
from vnalpha.data_availability.policy import DataAvailabilityPolicy


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
        feature_snapshot_exists=get_feature_snapshot_status(conn, symbol, target_date),
        candidate_score_exists=score_evidence.exists,
        candidate_score_as_of_date=score_evidence.as_of_bar_date,
        quality_status=score_evidence.quality_status,
        lineage_fields=score_evidence.lineage_fields,
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
            get_feature_snapshot_evidence(conn, symbol, target_date),
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
    canonical_will_be_built = canonical_missing and policy.auto_sync
    if canonical_will_be_built:
        actions.extend(
            (EnsureDataAction.OHLCV_SYNCED, EnsureDataAction.CANONICAL_BUILT)
        )

    benchmark_missing = (
        policy.require_benchmark_history
        and snapshot.benchmark_bars < policy.min_required_bars
    )
    if benchmark_missing and policy.auto_sync:
        actions.extend(
            (
                EnsureDataAction.BENCHMARK_SYNCED,
                EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
            )
        )

    feature_can_be_built = (
        snapshot.canonical_bars >= policy.min_required_bars or canonical_will_be_built
    )
    feature_will_be_built = (
        policy.auto_sync
        and not snapshot.feature_snapshot_exists
        and feature_can_be_built
    )
    if feature_will_be_built:
        actions.append(EnsureDataAction.FEATURES_BUILT)

    if policy.auto_sync and (snapshot.feature_snapshot_exists or feature_will_be_built):
        actions.append(EnsureDataAction.SCORED)

    return EnsureDataPlan(snapshot=snapshot, actions=tuple(actions))
