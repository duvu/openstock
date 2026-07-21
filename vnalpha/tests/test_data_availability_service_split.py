from __future__ import annotations

from vnalpha.data_availability.models import (
    EnsureDataAction,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy


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
    )
