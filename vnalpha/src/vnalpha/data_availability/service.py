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


@dataclass(frozen=True, slots=True)
class NormalizedEnsureRequest:
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
    normalised_request = NormalizedEnsureRequest(
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
        eligibility = evaluate_cache_eligibility(snapshot, request.policy)
        if eligibility.eligible:
            return cache_hit_result(result, snapshot)
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
            return missing_symbol_result(result)

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
