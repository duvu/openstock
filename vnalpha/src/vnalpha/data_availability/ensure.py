"""Data availability ensure — deterministic provisioning before symbol analysis.

ensure_symbol_analysis_ready(conn, symbol, target_date, *, policy)

Steps:
  1. Normalize symbol/date, compute lookback_start
  2. Emit DATA_ENSURE_STARTED
  3. Cache hit if candidate_score is fresh → READY
  4. Check symbol_master; sync if missing and auto_sync
  5. Check canonical OHLCV; sync+build if missing/stale and auto_sync
  6. Check benchmark OHLCV; sync+build if missing/stale and auto_sync
  7. Check feature_snapshot; build if missing and canonical sufficient
  8. Check candidate_score; score if missing and features exist
  9. Final check → READY / PARTIAL / FAILED
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.data_availability.checks import (
    compute_lookback_start,
    get_benchmark_status,
    get_candidate_score_status,
    get_canonical_ohlcv_status,
    get_feature_snapshot_status,
    get_symbol_master_status,
)
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.data_availability.observability import (
    log_ensure_benchmark_sync_failed,
    log_ensure_benchmark_sync_started,
    log_ensure_benchmark_sync_succeeded,
    log_ensure_cache_hit,
    log_ensure_canonical_build_failed,
    log_ensure_canonical_build_started,
    log_ensure_canonical_build_succeeded,
    log_ensure_failed,
    log_ensure_feature_build_failed,
    log_ensure_feature_build_started,
    log_ensure_feature_build_succeeded,
    log_ensure_ohlcv_sync_failed,
    log_ensure_ohlcv_sync_started,
    log_ensure_ohlcv_sync_succeeded,
    log_ensure_partial,
    log_ensure_ready,
    log_ensure_score_failed,
    log_ensure_score_started,
    log_ensure_score_succeeded,
    log_ensure_started,
    log_ensure_symbols_sync_failed,
    log_ensure_symbols_sync_started,
    log_ensure_symbols_sync_succeeded,
)
from vnalpha.data_availability.policy import DEFAULT_POLICY, DataAvailabilityPolicy

logger = get_logger("data_availability.ensure")


def ensure_symbol_analysis_ready(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
    *,
    policy: DataAvailabilityPolicy = DEFAULT_POLICY,
    # Dependency-injection hooks for testability (default to real implementations)
    _sync_symbols_fn: Optional[Callable] = None,
    _sync_ohlcv_fn: Optional[Callable] = None,
    _sync_index_fn: Optional[Callable] = None,
    _build_canonical_fn: Optional[Callable] = None,
    _build_features_fn: Optional[Callable] = None,
    _score_universe_fn: Optional[Callable] = None,
) -> EnsureDataResult:
    """Ensure all data required to analyse *symbol* on *target_date* is present.

    Returns an EnsureDataResult describing what was done and the final status.
    All failures are best-effort: a single step failing degrades to PARTIAL/FAILED
    but never raises to the caller.
    """
    # Normalise inputs
    symbol = symbol.upper().strip()
    try:
        from datetime import date as DateType

        DateType.fromisoformat(target_date)
    except (ValueError, TypeError):
        target_date = datetime.now(timezone.utc).date().isoformat()

    result = EnsureDataResult(
        symbol=symbol, target_date=target_date, status=EnsureDataStatus.FAILED
    )

    # Compute lookback window
    lookback_start = compute_lookback_start(target_date, policy.lookback_days)

    try:
        log_ensure_started(symbol, target_date)
    except Exception:  # noqa: BLE001
        pass

    # Step 3 — Cache hit
    candidate_class = get_candidate_score_status(
        conn, symbol, target_date, policy.stale_after_calendar_days
    )
    if candidate_class is not None:
        result.candidate_score_exists = True
        result.feature_snapshot_exists = get_feature_snapshot_status(
            conn, symbol, target_date
        )
        result.canonical_bars = get_canonical_ohlcv_status(
            conn, symbol, target_date, lookback_start
        )
        result.actions_taken = [EnsureDataAction.CACHE_HIT]
        result.status = EnsureDataStatus.READY
        try:
            log_ensure_cache_hit(symbol, target_date)
        except Exception:  # noqa: BLE001
            pass
        return result

    # Step 4 — symbol_master check
    symbol_known = get_symbol_master_status(conn, symbol)
    if not symbol_known:
        if policy.auto_sync:
            try:
                log_ensure_symbols_sync_started(symbol)
                sync_fn = _sync_symbols_fn or _get_sync_symbols()
                sync_fn(conn)
                result.actions_taken.append(EnsureDataAction.SYMBOLS_SYNCED)
                symbol_known = get_symbol_master_status(conn, symbol)
                log_ensure_symbols_sync_succeeded(symbol)
            except Exception as exc:
                result.warnings.append(f"symbol_master sync failed: {exc}")
                try:
                    log_ensure_symbols_sync_failed(symbol, exc)
                except Exception:  # noqa: BLE001
                    pass
                logger.warning("symbol_master sync failed for %s: %s", symbol, exc)
        if not symbol_known:
            result.errors.append(f"Symbol '{symbol}' not found in symbol_master.")
            result.status = EnsureDataStatus.FAILED
            try:
                log_ensure_failed(symbol, target_date, result.errors)
            except Exception:  # noqa: BLE001
                pass
            return result

    # Step 5 — canonical OHLCV
    canonical_bars = get_canonical_ohlcv_status(
        conn, symbol, target_date, lookback_start
    )
    if canonical_bars < policy.min_required_bars and policy.auto_sync:
        # Sync raw OHLCV
        try:
            log_ensure_ohlcv_sync_started(symbol)
            sync_ohlcv_fn = _sync_ohlcv_fn or _get_sync_ohlcv()
            ohlcv_result = sync_ohlcv_fn(
                conn, universe=[symbol], start=lookback_start, end=target_date
            )
            inserted = ohlcv_result.get("inserted", 0)
            result.actions_taken.append(EnsureDataAction.OHLCV_SYNCED)
            log_ensure_ohlcv_sync_succeeded(symbol, inserted)
        except Exception as exc:
            result.warnings.append(f"OHLCV sync failed: {exc}")
            try:
                log_ensure_ohlcv_sync_failed(symbol, exc)
            except Exception:  # noqa: BLE001
                pass
            logger.warning("OHLCV sync failed for %s: %s", symbol, exc)

        # Build canonical from raw
        try:
            log_ensure_canonical_build_started(symbol)
            build_canonical_fn = _build_canonical_fn or _get_build_canonical()
            canonical_result = build_canonical_fn(conn, symbol=symbol)
            upserted = canonical_result.get("upserted", 0)
            result.actions_taken.append(EnsureDataAction.CANONICAL_BUILT)
            log_ensure_canonical_build_succeeded(symbol, upserted)
        except Exception as exc:
            result.warnings.append(f"Canonical build failed: {exc}")
            try:
                log_ensure_canonical_build_failed(symbol, exc)
            except Exception:  # noqa: BLE001
                pass
            logger.warning("Canonical build failed for %s: %s", symbol, exc)

        canonical_bars = get_canonical_ohlcv_status(
            conn, symbol, target_date, lookback_start
        )

    result.canonical_bars = canonical_bars

    if canonical_bars < policy.min_required_bars:
        result.warnings.append(
            f"Insufficient canonical bars: {canonical_bars} < {policy.min_required_bars} required."
        )

    # Step 6 — benchmark OHLCV
    benchmark = policy.benchmark
    benchmark_bars = get_benchmark_status(conn, benchmark, target_date, lookback_start)
    if benchmark_bars < policy.min_required_bars and policy.auto_sync:
        try:
            log_ensure_benchmark_sync_started(benchmark)
            sync_index_fn = _sync_index_fn or _get_sync_index()
            index_result = sync_index_fn(
                conn, symbol=benchmark, start=lookback_start, end=target_date
            )
            inserted = index_result.get("inserted", 0)
            result.actions_taken.append(EnsureDataAction.BENCHMARK_SYNCED)
            log_ensure_benchmark_sync_succeeded(benchmark, inserted)
        except Exception as exc:
            result.warnings.append(f"Benchmark sync failed: {exc}")
            try:
                log_ensure_benchmark_sync_failed(benchmark, exc)
            except Exception:  # noqa: BLE001
                pass
            logger.warning("Benchmark sync failed for %s: %s", benchmark, exc)

        # Build canonical for benchmark
        try:
            log_ensure_canonical_build_started(benchmark)
            build_canonical_fn = _build_canonical_fn or _get_build_canonical()
            bm_canonical = build_canonical_fn(conn, symbol=benchmark)
            result.actions_taken.append(EnsureDataAction.BENCHMARK_CANONICAL_BUILT)
            log_ensure_canonical_build_succeeded(
                benchmark, bm_canonical.get("upserted", 0)
            )
        except Exception as exc:
            result.warnings.append(f"Benchmark canonical build failed: {exc}")
            try:
                log_ensure_canonical_build_failed(benchmark, exc)
            except Exception:  # noqa: BLE001
                pass
            logger.warning(
                "Benchmark canonical build failed for %s: %s", benchmark, exc
            )

        benchmark_bars = get_benchmark_status(
            conn, benchmark, target_date, lookback_start
        )

    if benchmark_bars < policy.min_required_bars:
        result.warnings.append(
            f"Benchmark '{benchmark}' has insufficient bars: {benchmark_bars}."
            " RS features will be NaN."
        )

    # Step 7 — feature_snapshot
    feature_exists = get_feature_snapshot_status(conn, symbol, target_date)
    if not feature_exists and canonical_bars >= policy.min_required_bars:
        try:
            log_ensure_feature_build_started(symbol)
            build_features_fn = _build_features_fn or _get_build_features()
            build_features_fn(
                conn,
                target_date=target_date,
                universe=[symbol],
                benchmark_symbol=benchmark,
            )
            result.actions_taken.append(EnsureDataAction.FEATURES_BUILT)
            feature_exists = get_feature_snapshot_status(conn, symbol, target_date)
            log_ensure_feature_build_succeeded(symbol)
        except Exception as exc:
            result.warnings.append(f"Feature build failed: {exc}")
            try:
                log_ensure_feature_build_failed(symbol, exc)
            except Exception:  # noqa: BLE001
                pass
            logger.warning("Feature build failed for %s: %s", symbol, exc)

    result.feature_snapshot_exists = feature_exists

    # Step 8 — candidate_score
    score_exists = get_candidate_score_status(
        conn, symbol, target_date, policy.stale_after_calendar_days
    )
    if score_exists is None and feature_exists:
        try:
            log_ensure_score_started(symbol)
            score_fn = _score_universe_fn or _get_score_universe()
            score_fn(conn, date=target_date, universe=[symbol])
            result.actions_taken.append(EnsureDataAction.SCORED)
            score_exists = get_candidate_score_status(
                conn, symbol, target_date, policy.stale_after_calendar_days
            )
            log_ensure_score_succeeded(symbol)
        except Exception as exc:
            result.warnings.append(f"Scoring failed: {exc}")
            try:
                log_ensure_score_failed(symbol, exc)
            except Exception:  # noqa: BLE001
                pass
            logger.warning("Scoring failed for %s: %s", symbol, exc)

    result.candidate_score_exists = score_exists is not None

    # Step 9 — determine final status
    action_names = [a.value for a in result.actions_taken]
    if result.errors:
        result.status = EnsureDataStatus.FAILED
        try:
            log_ensure_failed(symbol, target_date, result.errors)
        except Exception:  # noqa: BLE001
            pass
    elif result.candidate_score_exists:
        result.status = EnsureDataStatus.READY
        try:
            log_ensure_ready(symbol, target_date, action_names)
        except Exception:  # noqa: BLE001
            pass
    else:
        result.status = EnsureDataStatus.PARTIAL
        if not result.warnings:
            result.warnings.append("Candidate score not available after provisioning.")
        try:
            log_ensure_partial(symbol, target_date, result.warnings)
        except Exception:  # noqa: BLE001
            pass

    return result


# ---------------------------------------------------------------------------
# Lazy import helpers (avoids circular imports at module load time)
# ---------------------------------------------------------------------------


def _get_sync_symbols():
    from vnalpha.ingestion.sync_symbols import sync_symbols

    return sync_symbols


def _get_sync_ohlcv():
    from vnalpha.ingestion.sync_ohlcv import sync_ohlcv

    return sync_ohlcv


def _get_sync_index():
    from vnalpha.ingestion.sync_index import sync_index_ohlcv

    return sync_index_ohlcv


def _get_build_canonical():
    from vnalpha.ingestion.build_canonical import build_canonical_ohlcv

    return build_canonical_ohlcv


def _get_build_features():
    from vnalpha.features.build_features import build_features

    return build_features


def _get_score_universe():
    from vnalpha.scoring.generate_watchlist import score_universe

    return score_universe
