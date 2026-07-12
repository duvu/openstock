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
        source: Provider source name override (e.g. 'VCI', 'TCBS'). None = default.
        base_url: Override vnstock-service base URL. None = default from config.
    """

    benchmark: str = "VNINDEX"
    lookback_days: int = 420
    min_required_bars: int = 120
    auto_sync: bool = True
    stale_after_calendar_days: int = 7
    require_benchmark_history: bool = True
    acceptable_quality_statuses: tuple[str, ...] = ("pass",)
    required_lineage_fields: tuple[str, ...] = (
        "as_of_bar_date",
        "scoring_version",
        "feature_build_version",
        "selected_provider",
        "ingestion_run_id",
    )
    source: str | None = None
    base_url: str | None = None


DEFAULT_POLICY = DataAvailabilityPolicy()
