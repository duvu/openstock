"""vnalpha shared types and enums."""
from __future__ import annotations

from enum import Enum
from typing import TypeAlias

DateStr: TypeAlias = str  # YYYY-MM-DD


class CandidateClass(str, Enum):
    """Canonical candidate classification values.

    Research-only: used for watchlist filtering and display.
    Do not use as trade signals.
    """
    # Canonical values (current)
    STRONG_CANDIDATE = "STRONG_CANDIDATE"
    WATCH_CANDIDATE = "WATCH_CANDIDATE"
    WEAK_CANDIDATE = "WEAK_CANDIDATE"
    IGNORE = "IGNORE"
    # Legacy aliases (deprecated — kept for backward compat only, do not use in new code)
    STAGE1 = "STAGE1"
    STAGE2 = "STAGE2"
    BREAKOUT = "BREAKOUT"
    MOMENTUM = "MOMENTUM"
    MEAN_REVERT = "MEAN_REVERT"


class SetupType(str, Enum):
    """Canonical setup-type classification values.

    Describes the observed chart pattern for research purposes.
    """
    # Canonical values (current)
    ACCUMULATION_BASE = "ACCUMULATION_BASE"
    BREAKOUT_ATTEMPT = "BREAKOUT_ATTEMPT"
    MOMENTUM_CONTINUATION = "MOMENTUM_CONTINUATION"
    PULLBACK_TO_TREND = "PULLBACK_TO_TREND"
    MEAN_REVERSION = "MEAN_REVERSION"
    UNCLASSIFIED = "UNCLASSIFIED"
    # Legacy aliases (deprecated — kept for backward compat only, do not use in new code)
    TREND_CONTINUATION = "TREND_CONTINUATION"
    BASE_BREAKOUT = "BASE_BREAKOUT"
    PULLBACK_TO_MA = "PULLBACK_TO_MA"
    VOLUME_SURGE = "VOLUME_SURGE"
    BASE_BREAKOUT_ATTEMPT = "BASE_BREAKOUT_ATTEMPT"
    PULLBACK_TO_MA20 = "PULLBACK_TO_MA20"
    RELATIVE_STRENGTH_LEADER = "RELATIVE_STRENGTH_LEADER"
    UNKNOWN = "UNKNOWN"


class RiskFlag(str, Enum):
    # Scoring engine v1 risk flags
    THIN_VOLUME = "THIN_VOLUME"
    HIGH_ATR = "HIGH_ATR"
    NEAR_RESISTANCE = "NEAR_RESISTANCE"
    OVERBOUGHT = "OVERBOUGHT"
    EXTENDED_FROM_MA = "EXTENDED_FROM_MA"
    # Legacy risk flags (kept for backward compat)
    EXTENDED_FROM_MA20 = "EXTENDED_FROM_MA20"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    WEAK_RS = "WEAK_RS"
    BAD_MARKET_REGIME = "BAD_MARKET_REGIME"
    POOR_DATA_QUALITY = "POOR_DATA_QUALITY"
    VOLUME_SPIKE_ABNORMAL = "VOLUME_SPIKE_ABNORMAL"
    MISSING_HISTORY = "MISSING_HISTORY"


class IngestionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class DataQualityStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"
