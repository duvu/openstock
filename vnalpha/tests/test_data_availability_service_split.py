from __future__ import annotations

import inspect
from pathlib import Path

import duckdb

from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.warehouse.migrations import run_migrations


def test_planning_is_side_effect_free_when_snapshot_has_missing_data() -> None:
    from vnalpha.data_availability.planner import (
        EnsureDataSnapshot,
        plan_data_availability,
    )

    snapshot = EnsureDataSnapshot(
        symbol="FPT",
        target_date="2025-06-30",
        lookback_start="2024-05-06",
        symbol_known=True,
        canonical_bars=0,
        benchmark_bars=0,
        feature_snapshot_exists=False,
        candidate_score_exists=False,
    )

    plan = plan_data_availability(
        snapshot,
        DataAvailabilityPolicy(auto_sync=True, min_required_bars=1),
    )

    assert snapshot.canonical_bars == 0
    assert plan.actions == (
        EnsureDataAction.OHLCV_SYNCED,
        EnsureDataAction.CANONICAL_BUILT,
        EnsureDataAction.BENCHMARK_SYNCED,
        EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
        EnsureDataAction.FEATURES_BUILT,
        EnsureDataAction.SCORED,
    )


def test_planning_includes_only_missing_actions() -> None:
    from vnalpha.data_availability.planner import (
        EnsureDataSnapshot,
        plan_data_availability,
    )

    snapshot = EnsureDataSnapshot(
        symbol="FPT",
        target_date="2025-06-30",
        lookback_start="2024-05-06",
        symbol_known=True,
        canonical_bars=120,
        benchmark_bars=120,
        feature_snapshot_exists=True,
        candidate_score_exists=False,
    )

    plan = plan_data_availability(snapshot, DataAvailabilityPolicy())

    assert plan.actions == (EnsureDataAction.SCORED,)


def test_service_executes_actions_in_order_after_partial_failure() -> None:
    from vnalpha.data_availability.service import execute_planned_actions

    calls: list[EnsureDataAction] = []

    def run(action: EnsureDataAction) -> None:
        calls.append(action)
        if action is EnsureDataAction.OHLCV_SYNCED:
            raise RuntimeError("provider unavailable")

    completed, warnings = execute_planned_actions(
        (
            EnsureDataAction.OHLCV_SYNCED,
            EnsureDataAction.CANONICAL_BUILT,
            EnsureDataAction.FEATURES_BUILT,
        ),
        run,
    )

    assert calls == [
        EnsureDataAction.OHLCV_SYNCED,
        EnsureDataAction.CANONICAL_BUILT,
        EnsureDataAction.FEATURES_BUILT,
    ]
    assert completed == [
        EnsureDataAction.CANONICAL_BUILT,
        EnsureDataAction.FEATURES_BUILT,
    ]
    assert warnings == ["OHLCV_SYNCED failed: provider unavailable"]


def test_service_returns_warning_after_vnstock_http_error() -> None:
    from vnalpha.clients.vnstock.errors import VnstockHTTPError
    from vnalpha.data_availability.service import execute_planned_actions

    def run(action: EnsureDataAction) -> None:
        raise VnstockHTTPError(503, "/v1/index/ohlcv", "unavailable")

    completed, warnings = execute_planned_actions(
        (EnsureDataAction.BENCHMARK_SYNCED, EnsureDataAction.FEATURES_BUILT),
        run,
    )

    assert completed == []
    assert warnings == [
        "BENCHMARK_SYNCED failed: HTTP 503 from /v1/index/ohlcv: unavailable",
        "FEATURES_BUILT failed: HTTP 503 from /v1/index/ohlcv: unavailable",
    ]


def test_legacy_wrapper_contains_unexpected_failure_and_releases_lock(
    tmp_path: Path,
) -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
    from vnalpha.data_availability.lock import EnsureLock

    class UnexpectedProviderFailure(Exception):
        pass

    conn = duckdb.connect()
    run_migrations(conn=conn)

    def sync_symbols(conn, **kwargs):
        raise UnexpectedProviderFailure("unexpected provider failure")

    result = ensure_symbol_analysis_ready(
        conn,
        "FPT",
        "2025-06-30",
        policy=DataAvailabilityPolicy(auto_sync=True),
        _sync_symbols_fn=sync_symbols,
        _lock_dir=tmp_path,
    )

    assert result.status is EnsureDataStatus.FAILED
    assert result.warnings == ["symbol_master sync failed: unexpected provider failure"]
    lock = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path)
    assert lock.acquire() is True
    lock.release()


def test_legacy_wrapper_preserves_all_dependency_injection_keywords() -> None:
    from vnalpha.data_availability import ensure_symbol_analysis_ready

    parameter_names = inspect.signature(ensure_symbol_analysis_ready).parameters

    assert {
        "policy",
        "client",
        "_sync_symbols_fn",
        "_sync_ohlcv_fn",
        "_sync_index_fn",
        "_build_canonical_fn",
        "_build_features_fn",
        "_score_universe_fn",
        "_lock_dir",
    } <= set(parameter_names)


def test_result_exposes_freshness_and_lineage_defaults() -> None:
    result = EnsureDataResult(
        symbol="FPT",
        target_date="2025-06-30",
        status=EnsureDataStatus.PARTIAL,
    )

    assert result.freshness == "unknown"
    assert result.lineage_actions == []


def test_service_skips_features_after_canonical_rebuild_still_lacks_bars() -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready

    conn = duckdb.connect()
    run_migrations(conn=conn)
    conn.execute(
        "INSERT INTO symbol_master (symbol, is_active, last_seen_at) "
        "VALUES ('FPT', TRUE, current_timestamp)"
    )
    feature_calls: list[str] = []

    def sync_ohlcv(conn, **kwargs):
        return {"inserted": 0}

    def build_canonical(conn, **kwargs):
        return {"upserted": 0}

    def build_features(conn, **kwargs):
        feature_calls.append("features")
        return {"built": 0}

    def sync_index(conn, **kwargs):
        return {"inserted": 0}

    ensure_symbol_analysis_ready(
        conn,
        "FPT",
        "2025-06-30",
        policy=DataAvailabilityPolicy(auto_sync=True, min_required_bars=1),
        _sync_ohlcv_fn=sync_ohlcv,
        _sync_index_fn=sync_index,
        _build_canonical_fn=build_canonical,
        _build_features_fn=build_features,
    )

    assert feature_calls == []
