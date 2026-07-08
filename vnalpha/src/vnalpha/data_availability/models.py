"""Data availability models — result types and status enums."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == EnsureDataStatus.READY

    def to_panel_dict(self) -> dict[str, Any]:
        """Return a dict suitable for a ResultPanel."""
        return {
            "status": self.status.value,
            "canonical_bars": self.canonical_bars,
            "feature_snapshot": self.feature_snapshot_exists,
            "candidate_score": self.candidate_score_exists,
            "actions_taken": [a.value for a in self.actions_taken],
            "warnings": self.warnings,
            "errors": self.errors,
        }
