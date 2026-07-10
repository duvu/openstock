"""Read-only availability snapshots and deterministic provisioning plans."""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from vnalpha.data_availability.checks import (
    compute_lookback_start,
    get_benchmark_status,
    get_candidate_score_status,
    get_canonical_ohlcv_status,
    get_feature_snapshot_status,
    get_symbol_master_status,
)
from vnalpha.data_availability.models import EnsureDataAction
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
    return EnsureDataSnapshot(
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
        candidate_score_exists=(
            get_candidate_score_status(
                conn, symbol, target_date, policy.stale_after_calendar_days
            )
            is not None
        ),
    )


def plan_data_availability(
    snapshot: EnsureDataSnapshot, policy: DataAvailabilityPolicy
) -> EnsureDataPlan:
    """Return the ordered actions required by a read-only snapshot."""

    if snapshot.candidate_score_exists:
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

    benchmark_missing = snapshot.benchmark_bars < policy.min_required_bars
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
        not snapshot.feature_snapshot_exists and feature_can_be_built
    )
    if feature_will_be_built:
        actions.append(EnsureDataAction.FEATURES_BUILT)

    if snapshot.feature_snapshot_exists or feature_will_be_built:
        actions.append(EnsureDataAction.SCORED)

    return EnsureDataPlan(snapshot=snapshot, actions=tuple(actions))
