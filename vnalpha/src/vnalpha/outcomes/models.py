"""Outcome tracking domain models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Final, List, Optional

FORWARD_OUTCOME_MEASUREMENT_CONTRACT_VERSION: Final = (
    "candidate-outcome-forward-return-v2"
)
OUTCOME_EVALUATION_ASSUMPTIONS_CONTRACT_VERSION: Final = (
    "outcome-evaluation-assumptions-v1"
)
OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD: Final = {
    "market_friction": (
        "No transaction costs, fees, slippage, or taxes are applied for held-out outcomes.",
    ),
    "eligibility": (
        "Only symbols and watch dates that pass the production-compatible feature "
        "pipeline are treated as eligible for held-out measurement.",
    ),
    "capacity": (
        "Evaluations assume no liquidity or capital-capacity constraints on entry size.",
    ),
}
OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD_JSON: Final = json.dumps(
    OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD,
    sort_keys=True,
    separators=(",", ":"),
)
OUTCOME_EVALUATION_ASSUMPTIONS_HASH: Final = hashlib.sha256(
    OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD_JSON.encode("utf-8")
).hexdigest()


class OutcomeStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    MISSING_DATA = "MISSING_DATA"
    ERROR = "ERROR"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class HypothesisOutcomeSummary:
    selected_feature_rows: int
    eligible_feature_rows: int
    complete_observation_rows: int
    excluded_feature_rows: int
    missing_observation_rows: int
    mean_forward_return: float | None
    price_basis: str
    adjustment_methodology: str
    adjustment_version: str
    scoring_policy_hash: str | None


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
    symbol: str
    watchlist_date: str
    horizon_sessions: int
    rank: Optional[int] = None
    score: Optional[float] = None
    candidate_class: Optional[str] = None
    setup_type: Optional[str] = None
    risk_flags_json: Optional[str] = None
    observation_start_date: Optional[str] = None
    observation_end_date: Optional[str] = None
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
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None
    symbol_bar_count: Optional[int] = None
    benchmark_bar_count: Optional[int] = None
    price_basis: str = "UNKNOWN"
    benchmark_price_basis: str = "UNKNOWN"
    adjustment_methodology: str = "UNKNOWN"
    adjustment_version: str = "UNKNOWN"
    factor_chain_hash: Optional[str] = None
    action_overlap_status: str = "NOT_EVALUATED"
    invalidation_reason: Optional[str] = None
    corporate_action_lineage_json: str = "[]"
    scoring_policy_id: Optional[str] = None
    scoring_policy_version: Optional[str] = None
    scoring_policy_hash: Optional[str] = None
    scoring_policy_status: Optional[str] = None
    ranking_run_ref: Optional[str] = None
    eligible_universe_hash: Optional[str] = None


@dataclass
class WatchlistOutcomeRecord:
    watchlist_date: str
    horizon_sessions: int
    candidate_count: Optional[int] = None
    complete_count: Optional[int] = None
    pending_count: Optional[int] = None
    missing_data_count: Optional[int] = None
    invalid_count: Optional[int] = None
    avg_forward_return: Optional[float] = None
    median_forward_return: Optional[float] = None
    avg_excess_return: Optional[float] = None
    median_excess_return: Optional[float] = None
    avg_max_gain: Optional[float] = None
    avg_max_drawdown: Optional[float] = None
    hit_rate: Optional[float] = None
    failure_rate: Optional[float] = None
    computed_at: Optional[str] = None
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None
    price_basis: str = "UNKNOWN"
    adjustment_methodology: str = "UNKNOWN"
    adjustment_version: str = "UNKNOWN"
    action_overlap_status: str = "NOT_EVALUATED"
    scoring_policy_id: Optional[str] = None
    scoring_policy_version: Optional[str] = None
    scoring_policy_hash: Optional[str] = None
    scoring_policy_status: Optional[str] = None


@dataclass
class ScoreBucketPerformanceRecord:
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
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None
    price_basis: str = "UNKNOWN"
    adjustment_methodology: str = "UNKNOWN"
    adjustment_version: str = "UNKNOWN"
    action_overlap_status: str = "NOT_EVALUATED"
    scoring_policy_id: Optional[str] = None
    scoring_policy_version: Optional[str] = None
    scoring_policy_hash: Optional[str] = None
    scoring_policy_status: Optional[str] = None


@dataclass
class SetupTypePerformanceRecord:
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
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None
    price_basis: str = "UNKNOWN"
    adjustment_methodology: str = "UNKNOWN"
    adjustment_version: str = "UNKNOWN"
    action_overlap_status: str = "NOT_EVALUATED"
    scoring_policy_id: Optional[str] = None
    scoring_policy_version: Optional[str] = None
    scoring_policy_hash: Optional[str] = None
    scoring_policy_status: Optional[str] = None


@dataclass
class RiskFlagPerformanceRecord:
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
    evaluation_run_id: Optional[str] = None
    evaluator_version: Optional[str] = None
    metric_policy_version: Optional[str] = None
    price_basis: str = "UNKNOWN"
    adjustment_methodology: str = "UNKNOWN"
    adjustment_version: str = "UNKNOWN"
    action_overlap_status: str = "NOT_EVALUATED"
    scoring_policy_id: Optional[str] = None
    scoring_policy_version: Optional[str] = None
    scoring_policy_hash: Optional[str] = None
    scoring_policy_status: Optional[str] = None


__all__ = [
    "DEFAULT_HORIZONS",
    "FORWARD_OUTCOME_MEASUREMENT_CONTRACT_VERSION",
    "OUTCOME_EVALUATION_ASSUMPTIONS_CONTRACT_VERSION",
    "OUTCOME_EVALUATION_ASSUMPTIONS_HASH",
    "OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD",
    "OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD_JSON",
    "CandidateOutcomeRecord",
    "HypothesisOutcomeSummary",
    "OutcomeStatus",
    "RiskFlagPerformanceRecord",
    "SCORE_BUCKETS",
    "ScoreBucketPerformanceRecord",
    "SetupTypePerformanceRecord",
    "WatchlistOutcomeRecord",
    "assign_score_bucket",
]
