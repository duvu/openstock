"""Provisioning action dispatch and injectable dependency hooks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict, assert_never

import duckdb

from vnalpha.data_availability.models import EnsureDataAction
from vnalpha.data_availability.observability import (
    log_ensure_benchmark_sync_failed,
    log_ensure_benchmark_sync_started,
    log_ensure_benchmark_sync_succeeded,
    log_ensure_canonical_build_failed,
    log_ensure_canonical_build_started,
    log_ensure_canonical_build_succeeded,
    log_ensure_feature_build_failed,
    log_ensure_feature_build_started,
    log_ensure_feature_build_succeeded,
    log_ensure_ohlcv_sync_failed,
    log_ensure_ohlcv_sync_started,
    log_ensure_ohlcv_sync_succeeded,
    log_ensure_score_failed,
    log_ensure_score_started,
    log_ensure_score_succeeded,
    log_ensure_symbols_sync_failed,
    log_ensure_symbols_sync_started,
    log_ensure_symbols_sync_succeeded,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy

if TYPE_CHECKING:
    from vnalpha.clients.vnstock.client import VnstockClient

SyncAction = Callable[..., Mapping[str, int]]
BuildAction = Callable[..., Mapping[str, int]]
ScoreAction = Callable[..., int]


class RoutingKwargs(TypedDict, total=False):
    source: str
    base_url: str
    client: VnstockClient


@dataclass(frozen=True, slots=True)
class EnsureDependencies:
    sync_symbols: SyncAction | None = None
    sync_ohlcv: SyncAction | None = None
    sync_index: SyncAction | None = None
    build_canonical: BuildAction | None = None
    build_features: BuildAction | None = None
    score_universe: ScoreAction | None = None


@dataclass(frozen=True, slots=True)
class ActionContext:
    conn: duckdb.DuckDBPyConnection
    symbol: str
    target_date: str
    lookback_start: str
    policy: DataAvailabilityPolicy
    client: VnstockClient | None
    dependencies: EnsureDependencies


def execute_action(action: EnsureDataAction, context: ActionContext) -> None:
    """Execute one provision action and emit its success event."""

    match action:
        case EnsureDataAction.SYMBOLS_SYNCED:
            log_ensure_symbols_sync_started(context.symbol)
            _sync_symbols(context)
            log_ensure_symbols_sync_succeeded(context.symbol)
        case EnsureDataAction.OHLCV_SYNCED:
            log_ensure_ohlcv_sync_started(context.symbol)
            inserted = _sync_ohlcv(context)
            log_ensure_ohlcv_sync_succeeded(context.symbol, inserted)
        case EnsureDataAction.CANONICAL_BUILT:
            log_ensure_canonical_build_started(context.symbol)
            upserted = _build_canonical(context, context.symbol)
            log_ensure_canonical_build_succeeded(context.symbol, upserted)
        case EnsureDataAction.BENCHMARK_SYNCED:
            log_ensure_benchmark_sync_started(context.policy.benchmark)
            inserted = _sync_index(context)
            log_ensure_benchmark_sync_succeeded(context.policy.benchmark, inserted)
        case EnsureDataAction.BENCHMARK_CANONICAL_BUILT:
            benchmark = context.policy.benchmark
            log_ensure_canonical_build_started(benchmark)
            upserted = _build_canonical(context, benchmark)
            log_ensure_canonical_build_succeeded(benchmark, upserted)
        case EnsureDataAction.FEATURES_BUILT:
            log_ensure_feature_build_started(context.symbol)
            _build_features(context)
            log_ensure_feature_build_succeeded(context.symbol)
        case EnsureDataAction.SCORED:
            log_ensure_score_started(context.symbol)
            _score_universe(context)
            log_ensure_score_succeeded(context.symbol)
        case EnsureDataAction.CACHE_HIT:
            assert_never(action)
        case unreachable:
            assert_never(unreachable)


def log_action_failure(action: EnsureDataAction, symbol: str, error: Exception) -> None:
    """Emit the established failure event for one provision action."""

    match action:
        case EnsureDataAction.SYMBOLS_SYNCED:
            log_ensure_symbols_sync_failed(symbol, error)
        case EnsureDataAction.OHLCV_SYNCED:
            log_ensure_ohlcv_sync_failed(symbol, error)
        case EnsureDataAction.CANONICAL_BUILT:
            log_ensure_canonical_build_failed(symbol, error)
        case EnsureDataAction.BENCHMARK_SYNCED:
            log_ensure_benchmark_sync_failed(symbol, error)
        case EnsureDataAction.BENCHMARK_CANONICAL_BUILT:
            log_ensure_canonical_build_failed(symbol, error)
        case EnsureDataAction.FEATURES_BUILT:
            log_ensure_feature_build_failed(symbol, error)
        case EnsureDataAction.SCORED:
            log_ensure_score_failed(symbol, error)
        case EnsureDataAction.CACHE_HIT:
            assert_never(action)
        case unreachable:
            assert_never(unreachable)


def _routing_kwargs(context: ActionContext) -> RoutingKwargs:
    kwargs: RoutingKwargs = {}
    if context.policy.source:
        kwargs["source"] = context.policy.source
    if context.policy.base_url:
        kwargs["base_url"] = context.policy.base_url
    if context.client:
        kwargs["client"] = context.client
    return kwargs


def _sync_symbols(context: ActionContext) -> None:
    sync_symbols = context.dependencies.sync_symbols or _get_sync_symbols()
    sync_symbols(context.conn, **_routing_kwargs(context))


def _sync_ohlcv(context: ActionContext) -> int:
    sync_ohlcv = context.dependencies.sync_ohlcv or _get_sync_ohlcv()
    result = sync_ohlcv(
        context.conn,
        universe=[context.symbol],
        start=context.lookback_start,
        end=context.target_date,
        **_routing_kwargs(context),
    )
    return result.get("inserted", 0)


def _sync_index(context: ActionContext) -> int:
    sync_index = context.dependencies.sync_index or _get_sync_index()
    result = sync_index(
        context.conn,
        symbol=context.policy.benchmark,
        start=context.lookback_start,
        end=context.target_date,
        **_routing_kwargs(context),
    )
    return result.get("inserted", 0)


def _build_canonical(context: ActionContext, symbol: str) -> int:
    build_canonical = context.dependencies.build_canonical or _get_build_canonical()
    return build_canonical(context.conn, symbol=symbol).get("upserted", 0)


def _build_features(context: ActionContext) -> None:
    build_features = context.dependencies.build_features or _get_build_features()
    build_features(
        context.conn,
        target_date=context.target_date,
        universe=[context.symbol],
        benchmark_symbol=context.policy.benchmark,
    )


def _score_universe(context: ActionContext) -> None:
    score_universe = context.dependencies.score_universe or _get_score_universe()
    scored_rows = score_universe(
        context.conn, date=context.target_date, universe=[context.symbol]
    )
    if scored_rows < 1:
        raise RuntimeError("Scoring produced no row for the requested symbol.")


def _get_sync_symbols() -> SyncAction:
    from vnalpha.ingestion.sync_symbols import sync_symbols

    return sync_symbols


def _get_sync_ohlcv() -> SyncAction:
    from vnalpha.ingestion.sync_ohlcv import sync_ohlcv

    return sync_ohlcv


def _get_sync_index() -> SyncAction:
    from vnalpha.ingestion.sync_index import sync_index_ohlcv

    return sync_index_ohlcv


def _get_build_canonical() -> BuildAction:
    from vnalpha.ingestion.build_canonical import build_canonical_ohlcv

    return build_canonical_ohlcv


def _get_build_features() -> BuildAction:
    from vnalpha.features.build_features import build_features

    return build_features


def _get_score_universe() -> ScoreAction:
    from vnalpha.scoring.generate_watchlist import score_universe

    return score_universe
