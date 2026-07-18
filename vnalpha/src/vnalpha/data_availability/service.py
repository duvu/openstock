"""Locked data-availability service that executes deterministic plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import duckdb

from vnalpha.data_availability.actions import (
    ActionContext,
    EnsureDependencies,
    execute_action,
    log_action_failure,
)
from vnalpha.data_availability.cache import evaluate_cache_eligibility
from vnalpha.data_availability.dates import normalize_optional_date
from vnalpha.data_availability.lock import EnsureLock
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataActionOutcome,
    EnsureDataActionStatus,
    EnsureDataResult,
    EnsureDataStatus,
    EvidenceIssue,
)
from vnalpha.data_availability.observability import (
    log_ensure_cache_rejected,
    log_ensure_started,
)
from vnalpha.data_availability.planner import (
    EnsureDataSnapshot,
    capture_availability_snapshot,
    plan_data_availability,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_availability.raw_evidence import get_raw_ohlcv_window_evidence
from vnalpha.data_availability.results import (
    cache_hit_result,
    finalise_result,
    missing_symbol_result,
)

if TYPE_CHECKING:
    from vnalpha.clients.vnstock.client import VnstockClient

_PROVISION_ACTIONS: Final[tuple[EnsureDataAction, ...]] = (
    EnsureDataAction.OHLCV_SYNCED,
    EnsureDataAction.CANONICAL_BUILT,
    EnsureDataAction.BENCHMARK_SYNCED,
    EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
)


@dataclass(frozen=True, slots=True)
class EnsureRequest:
    conn: duckdb.DuckDBPyConnection
    symbol: str
    target_date: str | None
    policy: DataAvailabilityPolicy
    client: VnstockClient | None
    lock_dir: Path | None
    force_refresh: bool = False


@dataclass(frozen=True, slots=True)
class NormalizedEnsureRequest:
    conn: duckdb.DuckDBPyConnection
    symbol: str
    target_date: str
    policy: DataAvailabilityPolicy
    client: VnstockClient | None
    lock_dir: Path | None
    force_refresh: bool = False


def execute_planned_actions(
    actions: tuple[EnsureDataAction, ...],
    runner: Callable[[EnsureDataAction], None],
    on_failure: Callable[[EnsureDataAction, Exception], None] | None = None,
) -> tuple[list[EnsureDataAction], list[str]]:
    """Run actions in order, retaining later actions after a partial failure."""

    completed: list[EnsureDataAction] = []
    warnings: list[str] = []
    for action in actions:
        try:
            runner(action)
        except Exception as exc:
            warnings.append(f"{action.value} failed: {exc}")
            if on_failure:
                on_failure(action, exc)
        else:
            completed.append(action)
    return completed, warnings


def ensure_data_availability(
    request: EnsureRequest, dependencies: EnsureDependencies
) -> EnsureDataResult:
    """Ensure symbol analysis data while retaining the established best-effort flow."""

    symbol, target_date = _normalise_inputs(request.symbol, request.target_date)
    normalised_request = NormalizedEnsureRequest(
        conn=request.conn,
        symbol=symbol,
        target_date=target_date,
        policy=request.policy,
        client=request.client,
        lock_dir=request.lock_dir,
        force_refresh=request.force_refresh,
    )
    result = EnsureDataResult(
        symbol=symbol, target_date=target_date, status=EnsureDataStatus.FAILED
    )
    lock = EnsureLock(symbol, target_date, lock_dir=request.lock_dir)
    if not lock.acquire():
        result.failure_code = "LOCK_CONTENDED"
        result.warnings.append(
            f"Another ensure flow is active for {symbol}/{target_date}. Skipping."
        )
        result.status = EnsureDataStatus.PARTIAL
        return result

    try:
        log_ensure_started(symbol, target_date)
        snapshot = _snapshot(normalised_request)
        eligibility = evaluate_cache_eligibility(snapshot, request.policy)
        if eligibility.eligible and not normalised_request.force_refresh:
            return cache_hit_result(result, snapshot, request.policy)
        if normalised_request.force_refresh and eligibility.eligible:
            result.cache_rejection_reasons.append("force_refresh")
            log_ensure_cache_rejected(symbol, target_date, ("force_refresh",))
        else:
            result.cache_rejection_reasons.extend(eligibility.reasons)
            log_ensure_cache_rejected(symbol, target_date, eligibility.reasons)

        first_plan = plan_data_availability(snapshot, request.policy)
        _run_actions(
            tuple(
                action
                for action in first_plan.actions
                if action is EnsureDataAction.SYMBOLS_SYNCED
            ),
            normalised_request,
            dependencies,
            result,
        )
        snapshot = _snapshot(normalised_request)
        if not snapshot.symbol_known:
            return missing_symbol_result(result, snapshot, request.policy)

        plan = plan_data_availability(snapshot, normalised_request.policy)
        provision_actions = tuple(
            action for action in plan.actions if action in _PROVISION_ACTIONS
        )
        if normalised_request.force_refresh:
            provision_actions = _augment_refresh_provision_actions(
                provision_actions, snapshot, normalised_request.policy
            )
        _run_actions(provision_actions, normalised_request, dependencies, result)
        core_actions_completed = any(
            outcome.action in _PROVISION_ACTIONS
            and outcome.status is EnsureDataActionStatus.SUCCESS
            for outcome in result.action_outcomes
        )
        snapshot = _snapshot(normalised_request)
        feature_plan = plan_data_availability(snapshot, normalised_request.policy)
        feature_actions = tuple(
            action
            for action in feature_plan.actions
            if action is EnsureDataAction.FEATURES_BUILT
        )
        if (
            normalised_request.policy.auto_sync
            and (normalised_request.force_refresh or core_actions_completed)
            and not any(action in _PROVISION_ACTIONS for action in feature_plan.actions)
        ):
            feature_actions = (EnsureDataAction.FEATURES_BUILT,)
        _run_actions(
            feature_actions,
            normalised_request,
            dependencies,
            result,
        )
        snapshot = _snapshot(normalised_request)
        score_plan = plan_data_availability(snapshot, normalised_request.policy)
        score_actions = tuple(
            action for action in score_plan.actions if action is EnsureDataAction.SCORED
        )
        feature_refresh_completed = any(
            outcome.action is EnsureDataAction.FEATURES_BUILT
            and outcome.status is EnsureDataActionStatus.SUCCESS
            for outcome in result.action_outcomes
        )
        if normalised_request.force_refresh and feature_refresh_completed:
            score_actions = (EnsureDataAction.SCORED,)
        _run_actions(
            score_actions,
            normalised_request,
            dependencies,
            result,
        )
        final_snapshot = _snapshot(normalised_request)
        return finalise_result(result, final_snapshot, normalised_request.policy)
    finally:
        lock.release()


def _normalise_inputs(symbol: str, target_date: str | None) -> tuple[str, str]:
    normalised_symbol = symbol.upper().strip()
    return normalised_symbol, normalize_optional_date(target_date)


def _snapshot(request: NormalizedEnsureRequest) -> EnsureDataSnapshot:
    return capture_availability_snapshot(
        request.conn, request.symbol, request.target_date, request.policy
    )


def _action_context(
    request: NormalizedEnsureRequest,
    snapshot: EnsureDataSnapshot,
    dependencies: EnsureDependencies,
) -> ActionContext:
    return ActionContext(
        conn=request.conn,
        symbol=request.symbol,
        target_date=request.target_date,
        lookback_start=snapshot.lookback_start,
        policy=request.policy,
        client=request.client,
        dependencies=dependencies,
    )


def _augment_refresh_provision_actions(
    planned: tuple[EnsureDataAction, ...],
    snapshot: EnsureDataSnapshot,
    policy: DataAvailabilityPolicy,
) -> tuple[EnsureDataAction, ...]:
    """Add bounded incremental OHLCV/canonical refresh when data already exists.

    An explicit refresh performs bounded incremental work even when the snapshot
    would otherwise be treated as fresh. It never downgrades the auto-sync policy
    and it only adds work for symbols/benchmarks already present.
    """

    if not policy.auto_sync:
        return planned
    actions = list(planned)
    if snapshot.canonical_bars >= policy.min_required_bars:
        for action in (
            EnsureDataAction.OHLCV_SYNCED,
            EnsureDataAction.CANONICAL_BUILT,
        ):
            if action not in actions:
                actions.append(action)
    if (
        policy.require_benchmark_history
        and snapshot.benchmark_bars >= policy.min_required_bars
    ):
        for action in (
            EnsureDataAction.BENCHMARK_SYNCED,
            EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
        ):
            if action not in actions:
                actions.append(action)
    ordered = tuple(action for action in _PROVISION_ACTIONS if action in actions)
    return ordered


def _run_actions(
    actions: tuple[EnsureDataAction, ...],
    request: NormalizedEnsureRequest,
    dependencies: EnsureDependencies,
    result: EnsureDataResult,
) -> None:
    failed: list[EnsureDataAction] = []

    def on_failure(action: EnsureDataAction, error: Exception) -> None:
        failed.append(action)
        log_action_failure(action, request.symbol, error)

    def run_and_verify(action: EnsureDataAction) -> None:
        before = _snapshot(request)
        execute_action(action, _action_context(request, before, dependencies))
        after = _snapshot(request)
        if not _action_postcondition_satisfied(action, request, after):
            raise RuntimeError(
                f"{action.value} postcondition was not satisfied after reload."
            )

    completed, warnings = execute_planned_actions(
        actions,
        run_and_verify,
        on_failure,
    )
    result.actions_taken.extend(completed)
    result.action_outcomes.extend(
        EnsureDataActionOutcome(
            action=action,
            status=(
                EnsureDataActionStatus.FAILED
                if action in failed
                else EnsureDataActionStatus.SUCCESS
            ),
        )
        for action in actions
    )
    result.warnings.extend(_legacy_warning(warning) for warning in warnings)


def _action_postcondition_satisfied(
    action: EnsureDataAction,
    request: NormalizedEnsureRequest,
    snapshot: EnsureDataSnapshot,
) -> bool:
    policy = request.policy
    issues = set(evaluate_cache_eligibility(snapshot, policy).issues)
    match action:
        case EnsureDataAction.SYMBOLS_SYNCED:
            return snapshot.symbol_known
        case EnsureDataAction.OHLCV_SYNCED:
            return _raw_window_ready(
                snapshot.raw_ohlcv_bars,
                snapshot.latest_raw_bar_date,
                snapshot.target_date,
                policy,
            )
        case EnsureDataAction.CANONICAL_BUILT:
            return (
                not issues.intersection(
                    {
                        EvidenceIssue.CANONICAL_HISTORY_INSUFFICIENT,
                        EvidenceIssue.CANONICAL_GAPS_UNRESOLVED,
                        EvidenceIssue.QUALITY_UNACCEPTABLE,
                    }
                )
                and snapshot.latest_canonical_bar_date == snapshot.target_date
            )
        case EnsureDataAction.BENCHMARK_SYNCED:
            evidence = get_raw_ohlcv_window_evidence(
                request.conn,
                policy.benchmark,
                snapshot.lookback_start,
                snapshot.target_date,
            )
            return _raw_window_ready(
                evidence.row_count,
                evidence.latest_bar_date,
                snapshot.target_date,
                policy,
            )
        case EnsureDataAction.BENCHMARK_CANONICAL_BUILT:
            return (
                EvidenceIssue.BENCHMARK_HISTORY_INSUFFICIENT not in issues
                and snapshot.latest_benchmark_bar_date == snapshot.target_date
            )
        case EnsureDataAction.FEATURES_BUILT:
            return not issues.intersection(
                {
                    EvidenceIssue.FEATURE_SNAPSHOT_MISSING,
                    EvidenceIssue.FEATURE_SNAPSHOT_INVALID,
                    EvidenceIssue.FEATURE_LINEAGE_INCOMPLETE,
                }
            )
        case EnsureDataAction.SCORED:
            return (
                not issues.intersection(
                    {
                        EvidenceIssue.SCORE_MISSING,
                        EvidenceIssue.SCORE_STALE,
                        EvidenceIssue.LINEAGE_INCOMPLETE,
                    }
                )
                and snapshot.candidate_score_as_of_date == snapshot.target_date
            )
        case EnsureDataAction.CACHE_HIT:
            return True


def _raw_window_ready(
    row_count: int,
    latest_bar_date: str | None,
    target_date: str,
    policy: DataAvailabilityPolicy,
) -> bool:
    return row_count >= policy.min_required_bars and latest_bar_date == target_date


def _legacy_warning(warning: str) -> str:
    replacements = {
        "SYMBOLS_SYNCED": "symbol_master sync",
        "OHLCV_SYNCED": "OHLCV sync",
        "CANONICAL_BUILT": "Canonical build",
        "BENCHMARK_SYNCED": "Benchmark sync",
        "BENCHMARK_CANONICAL_BUILT": "Benchmark canonical build",
        "FEATURES_BUILT": "Feature build",
        "SCORED": "Scoring",
    }
    action, _, detail = warning.partition(" failed: ")
    return f"{replacements[action]} failed: {detail}"
