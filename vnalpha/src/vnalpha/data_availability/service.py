"""Locked data-availability service that executes deterministic plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as DateType
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Final

import duckdb

from vnalpha.data_availability.actions import (
    ActionContext,
    EnsureDependencies,
    execute_action,
    log_action_failure,
)
from vnalpha.data_availability.lock import EnsureLock
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.data_availability.observability import (
    log_ensure_cache_hit,
    log_ensure_failed,
    log_ensure_partial,
    log_ensure_ready,
    log_ensure_started,
)
from vnalpha.data_availability.planner import (
    EnsureDataSnapshot,
    capture_availability_snapshot,
    plan_data_availability,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy

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
    target_date: str
    policy: DataAvailabilityPolicy
    client: VnstockClient | None
    lock_dir: Path | None


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
    normalised_request = EnsureRequest(
        conn=request.conn,
        symbol=symbol,
        target_date=target_date,
        policy=request.policy,
        client=request.client,
        lock_dir=request.lock_dir,
    )
    result = EnsureDataResult(
        symbol=symbol, target_date=target_date, status=EnsureDataStatus.FAILED
    )
    lock = EnsureLock(symbol, target_date, lock_dir=request.lock_dir)
    if not lock.acquire():
        result.warnings.append(
            f"Another ensure flow is active for {symbol}/{target_date}. Skipping."
        )
        result.status = EnsureDataStatus.PARTIAL
        return result

    try:
        log_ensure_started(symbol, target_date)
        snapshot = _snapshot(normalised_request)
        if snapshot.candidate_score_exists:
            return _cache_hit(result, snapshot)

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
            return _missing_symbol(result, symbol, target_date)

        plan = plan_data_availability(snapshot, normalised_request.policy)
        context = _action_context(normalised_request, snapshot, dependencies)
        _run_actions(
            tuple(action for action in plan.actions if action in _PROVISION_ACTIONS),
            context,
            result,
        )
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
        _run_actions(
            tuple(
                action for action in feature_plan.actions if action in feature_actions
            ),
            context,
            result,
        )
        final_snapshot = _snapshot(normalised_request)
        return _finalise(result, final_snapshot, normalised_request.policy)
    finally:
        lock.release()


def _normalise_inputs(symbol: str, target_date: str) -> tuple[str, str]:
    normalised_symbol = symbol.upper().strip()
    try:
        DateType.fromisoformat(target_date)
    except (TypeError, ValueError):
        return normalised_symbol, datetime.now(timezone.utc).date().isoformat()
    return normalised_symbol, target_date


def _snapshot(request: EnsureRequest) -> EnsureDataSnapshot:
    return capture_availability_snapshot(
        request.conn, request.symbol, request.target_date, request.policy
    )


def _action_context(
    request: EnsureRequest,
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


def _cache_hit(
    result: EnsureDataResult, snapshot: EnsureDataSnapshot
) -> EnsureDataResult:
    result.canonical_bars = snapshot.canonical_bars
    result.feature_snapshot_exists = snapshot.feature_snapshot_exists
    result.candidate_score_exists = True
    result.actions_taken.append(EnsureDataAction.CACHE_HIT)
    result.freshness = "cache_hit"
    result.lineage_actions = [EnsureDataAction.CACHE_HIT.value]
    result.status = EnsureDataStatus.READY
    log_ensure_cache_hit(result.symbol, result.target_date)
    return result


def _missing_symbol(
    result: EnsureDataResult, symbol: str, target_date: str
) -> EnsureDataResult:
    result.errors.append(f"Symbol '{symbol}' not found in symbol_master.")
    result.status = EnsureDataStatus.FAILED
    log_ensure_failed(symbol, target_date, result.errors)
    return result


def _finalise(
    result: EnsureDataResult,
    snapshot: EnsureDataSnapshot,
    policy: DataAvailabilityPolicy,
) -> EnsureDataResult:
    result.canonical_bars = snapshot.canonical_bars
    result.feature_snapshot_exists = snapshot.feature_snapshot_exists
    result.candidate_score_exists = snapshot.candidate_score_exists
    result.lineage_actions = [action.value for action in result.actions_taken]
    if snapshot.canonical_bars < policy.min_required_bars:
        result.freshness = "missing_canonical"
    elif snapshot.candidate_score_exists:
        result.freshness = "ready"
    else:
        result.freshness = "partial"

    if snapshot.canonical_bars < policy.min_required_bars:
        result.warnings.append(
            "Insufficient canonical bars: "
            f"{snapshot.canonical_bars} < {policy.min_required_bars} required."
        )
    if snapshot.benchmark_bars < policy.min_required_bars:
        result.warnings.append(
            f"Benchmark '{policy.benchmark}' has insufficient bars: "
            f"{snapshot.benchmark_bars}. RS features will be NaN."
        )
    if not snapshot.candidate_score_exists:
        if not result.warnings:
            result.warnings.append("Candidate score not available after provisioning.")
        result.status = EnsureDataStatus.PARTIAL
        log_ensure_partial(result.symbol, result.target_date, result.warnings)
        return result

    result.status = EnsureDataStatus.READY
    log_ensure_ready(result.symbol, result.target_date, result.lineage_actions)
    return result
