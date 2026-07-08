"""Data availability policy — configuration for auto-provisioning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DataAvailabilityPolicy:
    """Policy controlling auto-provisioning behaviour.

    Attributes:
        benchmark: Symbol used as benchmark for relative-strength features.
        lookback_days: Calendar days of history to request when syncing OHLCV.
        min_required_bars: Minimum trading bars required to build features.
        auto_sync: If False, checks only — no syncs or builds are triggered.
        stale_after_calendar_days: A candidate_score older than this is considered
            stale and will be rebuilt.
    """

    benchmark: str = "VNINDEX"
    lookback_days: int = 420
    min_required_bars: int = 120
    auto_sync: bool = True
    stale_after_calendar_days: int = 7


DEFAULT_POLICY = DataAvailabilityPolicy()
