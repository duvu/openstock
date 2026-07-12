"""Backward-compatible entry point for data-availability provisioning."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

from vnalpha.data_availability.actions import EnsureDependencies
from vnalpha.data_availability.models import EnsureDataResult
from vnalpha.data_availability.policy import DEFAULT_POLICY, DataAvailabilityPolicy
from vnalpha.data_availability.service import EnsureRequest, ensure_data_availability

if TYPE_CHECKING:
    from collections.abc import Callable

    from vnalpha.clients.vnstock.client import VnstockClient


def ensure_symbol_analysis_ready(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str | None,
    *,
    policy: DataAvailabilityPolicy = DEFAULT_POLICY,
    client: VnstockClient | None = None,
    _sync_symbols_fn: Callable | None = None,
    _sync_ohlcv_fn: Callable | None = None,
    _sync_index_fn: Callable | None = None,
    _build_canonical_fn: Callable | None = None,
    _build_features_fn: Callable | None = None,
    _score_universe_fn: Callable | None = None,
    _lock_dir: Path | None = None,
) -> EnsureDataResult:
    """Preserve the legacy ensure API while routing through the service boundary."""

    request = EnsureRequest(
        conn=conn,
        symbol=symbol,
        target_date=target_date,
        policy=policy,
        client=client,
        lock_dir=_lock_dir,
    )
    dependencies = EnsureDependencies(
        sync_symbols=_sync_symbols_fn,
        sync_ohlcv=_sync_ohlcv_fn,
        sync_index=_sync_index_fn,
        build_canonical=_build_canonical_fn,
        build_features=_build_features_fn,
        score_universe=_score_universe_fn,
    )
    return ensure_data_availability(request, dependencies)
