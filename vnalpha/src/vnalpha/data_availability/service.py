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
    EnsureDataResult,
    EnsureDataStatus,
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
            return cache_hit_result(result, snapshot)
        if normalised_request.force_refresh and eligibility.eligible:
            result.cache_rejection_reasons.append("force_refresh")
            log_ensure_cache_rejected(symbol, target_date, ("force_refresh",))
        else:
            result.cache_rejection_reasons.extend(eligibility.reasons)
            log_ensure_cache_rejected(symbol, target_date, eligibility.reasons)

        first_plan = plan_data_availability(snapshot, request.policy)
        context = _action_context(normalised_request, snapshot, dependencies)
        _run_actions(
            tuple(
                action
                for action in first_plan.actions
                if action is EnsureDataAction.SYMBOLS_SYNCED
            ),
            context,
            result,
        )
        snapshot = _snapshot(normalised_request)
        if not snapshot.symbol_known:
            return missing_symbol_result(result, snapshot)

        plan = plan_data_availability(snapshot, normalised_request.policy)
        context = _action_context(normalised_request, snapshot, dependencies)
        provision_actions = tuple(
            action for action in plan.actions if action in _PROVISION_ACTIONS
        )
        if normalised_request.force_refresh:
            provision_actions = _augment_refresh_provision_actions(
                provision_actions, snapshot, normalised_request.policy
            )
        _run_actions(provision_actions, context, result)
        snapshot = _snapshot(normalised_request)
        feature_plan = plan_data_availability(snapshot, normalised_request.policy)
        context = _action_context(normalised_request, snapshot, dependencies)
        feature_actions: tuple[EnsureDataAction, ...] = ()
        if snapshot.feature_snapshot_exists:
            feature_actions = (EnsureDataAction.SCORED,)
        elif snapshot.canonical_bars >= normalised_request.policy.min_required_bars:
            feature_actions = (
                EnsureDataAction.FEATURES_BUILT,
                EnsureDataAction.SCORED,
            )
        if normalised_request.force_refresh:
            feature_actions = _augment_refresh_feature_actions(
                feature_actions, snapshot, normalised_request.policy
            )
        _run_actions(
            tuple(
                action for action in feature_plan.actions if action in feature_actions
            ),
            context,
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


def _augment_refresh_feature_actions(
    planned: tuple[EnsureDataAction, ...],
    snapshot: EnsureDataSnapshot,
    policy: DataAvailabilityPolicy,
) -> tuple[EnsureDataAction, ...]:
    """Rebuild features and re-score during an explicit refresh when possible."""

    if not policy.auto_sync:
        return planned
    if snapshot.canonical_bars >= policy.min_required_bars:
        return (EnsureDataAction.FEATURES_BUILT, EnsureDataAction.SCORED)
    return planned


def _run_actions(
    actions: tuple[EnsureDataAction, ...],
    context: ActionContext,
    result: EnsureDataResult,
) -> None:
    completed, warnings = execute_planned_actions(
        actions,
        lambda action: execute_action(action, context),
        lambda action, error: log_action_failure(action, context.symbol, error),
    )
    result.actions_taken.extend(completed)
    result.warnings.extend(_legacy_warning(warning) for warning in warnings)


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
