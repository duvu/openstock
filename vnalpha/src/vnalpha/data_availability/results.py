from __future__ import annotations

from vnalpha.data_availability.cache import evaluate_cache_eligibility
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataActionOutcome,
    EnsureDataActionStatus,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.data_availability.observability import (
    log_ensure_cache_hit,
    log_ensure_failed,
    log_ensure_partial,
    log_ensure_ready,
)
from vnalpha.data_availability.planner import EnsureDataSnapshot
from vnalpha.data_availability.policy import DataAvailabilityPolicy


def cache_hit_result(
    result: EnsureDataResult, snapshot: EnsureDataSnapshot
) -> EnsureDataResult:
    result.canonical_bars = snapshot.canonical_bars
    result.feature_snapshot_exists = snapshot.feature_snapshot_exists
    result.candidate_score_exists = True
    _record_snapshot_evidence(result, snapshot)
    result.actions_taken.append(EnsureDataAction.CACHE_HIT)
    result.action_outcomes.append(
        EnsureDataActionOutcome(
            action=EnsureDataAction.CACHE_HIT,
            status=EnsureDataActionStatus.SUCCESS,
        )
    )
    result.freshness = "cache_hit"
    result.lineage_actions = [EnsureDataAction.CACHE_HIT.value]
    result.status = EnsureDataStatus.READY
    log_ensure_cache_hit(result.symbol, result.target_date)
    return result


def missing_symbol_result(
    result: EnsureDataResult, snapshot: EnsureDataSnapshot
) -> EnsureDataResult:
    _record_snapshot_evidence(result, snapshot)
    result.symbol_known = False
    result.errors.append(f"Symbol '{result.symbol}' not found in symbol_master.")
    result.status = EnsureDataStatus.FAILED
    log_ensure_failed(result.symbol, result.target_date, result.errors)
    return result


def finalise_result(
    result: EnsureDataResult,
    snapshot: EnsureDataSnapshot,
    policy: DataAvailabilityPolicy,
) -> EnsureDataResult:
    eligibility = evaluate_cache_eligibility(snapshot, policy)
    result.canonical_bars = snapshot.canonical_bars
    result.feature_snapshot_exists = snapshot.feature_snapshot_exists
    result.candidate_score_exists = snapshot.candidate_score_exists
    _record_snapshot_evidence(result, snapshot)
    result.lineage_actions = [action.value for action in result.actions_taken]
    if snapshot.canonical_bars < policy.min_required_bars:
        result.freshness = "missing_canonical"
    elif eligibility.eligible:
        result.freshness = "ready"
    else:
        result.freshness = "partial"

    if snapshot.canonical_bars < policy.min_required_bars:
        result.warnings.append(
            "Insufficient canonical bars: "
            f"{snapshot.canonical_bars} < {policy.min_required_bars} required."
        )
    if snapshot.unresolved_true_gap_count > 0:
        result.warnings.append(
            "Unresolved canonical OHLCV gaps: "
            f"{snapshot.unresolved_true_gap_count}. Run a bounded OHLCV repair."
        )
    if (
        policy.require_benchmark_history
        and snapshot.benchmark_bars < policy.min_required_bars
    ):
        result.warnings.append(
            f"Benchmark '{policy.benchmark}' has insufficient bars: "
            f"{snapshot.benchmark_bars}. RS features will be NaN."
        )
    action_failed = any(
        outcome.status is EnsureDataActionStatus.FAILED
        for outcome in result.action_outcomes
    )
    if not eligibility.eligible or action_failed:
        if not result.warnings:
            result.warnings.append(
                "Candidate cache evidence remains incomplete: "
                + ", ".join(eligibility.reasons)
                + "."
            )
        result.extra["cache_eligibility_reasons"] = list(eligibility.reasons)
        result.status = EnsureDataStatus.PARTIAL
        log_ensure_partial(result.symbol, result.target_date, result.warnings)
        return result

    result.status = EnsureDataStatus.READY
    log_ensure_ready(result.symbol, result.target_date, result.lineage_actions)
    return result


def _record_snapshot_evidence(
    result: EnsureDataResult, snapshot: EnsureDataSnapshot
) -> None:
    result.symbol_known = snapshot.symbol_known
    result.benchmark_bars = snapshot.benchmark_bars
    result.candidate_score_as_of_date = snapshot.candidate_score_as_of_date
    result.quality_status = snapshot.quality_status
    result.lineage_fields = snapshot.lineage_fields
    result.artifact_evidence = snapshot.artifact_evidence
    result.core_evidence_evaluated = True
    result.extra["raw_window_ready"] = bool(
        snapshot.raw_ohlcv_bars >= 1
        and snapshot.latest_raw_bar_date == snapshot.target_date
    )
