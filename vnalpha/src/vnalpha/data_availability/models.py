"""Data availability models — result types and status enums."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


class EnsureDataStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class EnsureDataAction(str, Enum):
    CACHE_HIT = "CACHE_HIT"
    SYMBOLS_SYNCED = "SYMBOLS_SYNCED"
    OHLCV_SYNCED = "OHLCV_SYNCED"
    CANONICAL_BUILT = "CANONICAL_BUILT"
    BENCHMARK_SYNCED = "BENCHMARK_SYNCED"
    BENCHMARK_CANONICAL_BUILT = "BENCHMARK_CANONICAL_BUILT"
    FEATURES_BUILT = "FEATURES_BUILT"
    SCORED = "SCORED"


@dataclass(frozen=True, slots=True)
class CacheEligibility:
    eligible: bool
    reasons: tuple[str, ...]
    score_fresh: bool
    feature_present: bool
    canonical_sufficient: bool
    benchmark_sufficient: bool
    quality_acceptable: bool
    lineage_acceptable: bool


@dataclass
class EnsureDataResult:
    """Result from ensure_symbol_analysis_ready."""

    symbol: str
    target_date: str
    status: EnsureDataStatus
    actions_taken: list[EnsureDataAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # diagnostics for the panels
    canonical_bars: int = 0
    feature_snapshot_exists: bool = False
    candidate_score_exists: bool = False
    freshness: str = "unknown"
    lineage_actions: list[str] = field(default_factory=list)
    cache_rejection_reasons: list[str] = field(default_factory=list)
    extra: dict[str, JsonValue] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == EnsureDataStatus.READY

    def to_panel_dict(self) -> dict[str, JsonValue]:
        """Return a dict suitable for a ResultPanel."""
        return {
            "status": self.status.value,
            "canonical_bars": self.canonical_bars,
            "feature_snapshot": self.feature_snapshot_exists,
            "candidate_score": self.candidate_score_exists,
            "freshness": self.freshness,
            "lineage_actions": self.lineage_actions,
            "cache_rejection_reasons": self.cache_rejection_reasons,
            "actions_taken": [a.value for a in self.actions_taken],
            "warnings": self.warnings,
            "errors": self.errors,
        }
