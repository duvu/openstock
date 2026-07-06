"""Outcome tracking domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class OutcomeStatus(str, Enum):
    """Status of a candidate outcome evaluation."""

    COMPLETE = "COMPLETE"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    MISSING_DATA = "MISSING_DATA"
    ERROR = "ERROR"


DEFAULT_HORIZONS: List[int] = [5, 10, 20, 60]

SCORE_BUCKETS = [
    "0.00-0.40",
    "0.40-0.50",
    "0.50-0.60",
    "0.60-0.70",
    "0.70-0.80",
    "0.80-0.90",
    "0.90-1.00",
]


def assign_score_bucket(score: Optional[float]) -> str:
    """Return bucket label for a score value."""
    if score is None:
        return "0.00-0.40"
    if score >= 0.90:
        return "0.90-1.00"
    if score >= 0.80:
        return "0.80-0.90"
    if score >= 0.70:
        return "0.70-0.80"
    if score >= 0.60:
        return "0.60-0.70"
    if score >= 0.50:
        return "0.50-0.60"
    if score >= 0.40:
        return "0.40-0.50"
    return "0.00-0.40"


@dataclass
class CandidateOutcomeRecord:
    """Row from candidate_outcome table."""

    symbol: str
    watchlist_date: str
    horizon_sessions: int
    rank: Optional[int] = None
    score: Optional[float] = None
    candidate_class: Optional[str] = None
    setup_type: Optional[str] = None
    risk_flags_json: Optional[str] = None
    entry_close: Optional[float] = None
    exit_close: Optional[float] = None
    benchmark_entry_close: Optional[float] = None
    benchmark_exit_close: Optional[float] = None
    forward_return: Optional[float] = None
    benchmark_return: Optional[float] = None
    excess_return_vs_vnindex: Optional[float] = None
    max_gain: Optional[float] = None
    max_drawdown: Optional[float] = None
    hit: Optional[bool] = None
    failure: Optional[bool] = None
    outcome_status: str = OutcomeStatus.PENDING.value
    bars_available: Optional[int] = None
    required_bars: Optional[int] = None
    computed_at: Optional[str] = None
    error_json: Optional[str] = None
    # Versioning / traceability
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None
    symbol_bar_count: Optional[int] = None
    benchmark_bar_count: Optional[int] = None


@dataclass
class WatchlistOutcomeRecord:
    """Row from watchlist_outcome table."""

    watchlist_date: str
    horizon_sessions: int
    candidate_count: Optional[int] = None
    complete_count: Optional[int] = None
    pending_count: Optional[int] = None
    missing_data_count: Optional[int] = None
    avg_forward_return: Optional[float] = None
    median_forward_return: Optional[float] = None
    avg_excess_return: Optional[float] = None
    median_excess_return: Optional[float] = None
    avg_max_gain: Optional[float] = None
    avg_max_drawdown: Optional[float] = None
    hit_rate: Optional[float] = None
    failure_rate: Optional[float] = None
    computed_at: Optional[str] = None
    # Versioning / traceability
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None


@dataclass
class ScoreBucketPerformanceRecord:
    """Row from score_bucket_performance table."""

    as_of_date: str
    horizon_sessions: int
    score_bucket: str
    candidate_count: Optional[int] = None
    avg_forward_return: Optional[float] = None
    median_forward_return: Optional[float] = None
    avg_excess_return: Optional[float] = None
    hit_rate: Optional[float] = None
    failure_rate: Optional[float] = None
    avg_max_drawdown: Optional[float] = None
    computed_at: Optional[str] = None
    # Versioning / traceability
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None


@dataclass
class SetupTypePerformanceRecord:
    """Row from setup_type_performance table."""

    as_of_date: str
    horizon_sessions: int
    setup_type: str
    candidate_count: Optional[int] = None
    avg_forward_return: Optional[float] = None
    median_forward_return: Optional[float] = None
    avg_excess_return: Optional[float] = None
    hit_rate: Optional[float] = None
    failure_rate: Optional[float] = None
    avg_max_drawdown: Optional[float] = None
    computed_at: Optional[str] = None
    # Versioning / traceability
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None


@dataclass
class RiskFlagPerformanceRecord:
    """Row from risk_flag_performance table."""

    as_of_date: str
    horizon_sessions: int
    risk_flag: str
    candidate_count: Optional[int] = None
    avg_forward_return: Optional[float] = None
    median_forward_return: Optional[float] = None
    avg_excess_return: Optional[float] = None
    hit_rate: Optional[float] = None
    failure_rate: Optional[float] = None
    avg_max_drawdown: Optional[float] = None
    computed_at: Optional[str] = None
    # Versioning / traceability
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None
