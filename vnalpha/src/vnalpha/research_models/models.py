from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class MarketRegimeSnapshot:
    market_regime_snapshot_id: str
    as_of_date: date
    regime_state: str
    index_trend: str
    index_volatility: str
    breadth_summary: Mapping[str, Any]
    sector_strength_ref: str | None
    freshness: str
    lineage: Mapping[str, str]
    methodology_version: str
    correlation_id: str
    quality_status: str
    caveats: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SectorStrengthSnapshot:
    sector_strength_snapshot_id: str
    as_of_date: date
    sector: str
    rank: int
    relative_performance: float
    rotation_state: str
    breadth_proxy: Mapping[str, Any]
    member_count: int
    freshness: str
    lineage: Mapping[str, str]
    methodology_version: str
    correlation_id: str
    quality_status: str
    caveats: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SymbolLevelSnapshot:
    symbol_level_snapshot_id: str
    symbol: str
    as_of_date: date
    support_levels: tuple[float, ...]
    resistance_levels: tuple[float, ...]
    pivot_levels: tuple[float, ...]
    level_strength: Mapping[str, str]
    source_bar_refs: tuple[str, ...]
    freshness: str
    lineage: Mapping[str, str]
    methodology_version: str
    correlation_id: str
    quality_status: str
    caveats: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SetupAnalysis:
    setup_analysis_id: str
    symbol: str
    as_of_date: date
    setup_type: str
    setup_quality: str
    trend_context: str
    momentum_context: str
    relative_strength_context: str
    volume_context: str
    volatility_context: str
    level_snapshot_ref: str | None
    confidence: float
    freshness: str
    lineage: Mapping[str, str]
    methodology_version: str
    correlation_id: str
    quality_status: str
    caveats: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ShortlistCandidate:
    shortlist_candidate_id: str
    shortlist_run_id: str
    as_of_date: date
    rank: int
    symbol: str
    setup_type: str
    setup_quality: str
    shortlist_score: float
    why_shortlisted: tuple[str, ...]
    why_restrained: tuple[str, ...]
    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    risk_context: str
    freshness: str
    lineage: Mapping[str, str]
    methodology_version: str
    correlation_id: str
    quality_status: str
    caveats: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ShortlistDecisionReport:
    shortlist_decision_report_id: str
    shortlist_run_id: str
    as_of_date: date
    requested_limit: int
    requested_min_score: float
    considered_count: int
    shortlisted_count: int
    truncated_to_limit: bool
    artifact_refs: tuple[str, ...]
    missing_data: tuple[str, ...]
    validation_signature: str
    validation_checks: Mapping[str, Any]
    scoring_policy: Mapping[str, Any]
    freshness: str
    methodology_version: str
    lineage: Mapping[str, str]
    correlation_id: str
    quality_status: str
    caveats: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchScenarioPlan:
    scenario_plan_id: str
    symbol: str
    as_of_date: date
    current_setup: str
    key_levels: Mapping[str, float]
    scenario_tree: Mapping[str, Any]
    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    checklist: tuple[str, ...]
    risk_reward_estimate: str
    confidence: float
    caveats: tuple[str, ...]
    policy_classification: str
    freshness: str
    lineage: Mapping[str, str]
    methodology_version: str
    correlation_id: str
    quality_status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SetupEvidenceSnapshot:
    setup_evidence_snapshot_id: str
    setup_type: str
    as_of_date: date
    sample_definition: str
    horizon: str
    sample_size: int
    forward_return_distribution: Mapping[str, float]
    fae_aae_stats: Mapping[str, float]
    outcome_rate: float | None
    regime_split: Mapping[str, int]
    small_sample_caveat: str
    caveats: tuple[str, ...]
    freshness: str
    lineage: Mapping[str, str]
    methodology_version: str
    correlation_id: str
    quality_status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchAnswerAudit:
    answer_audit_id: str
    assistant_session_id: str
    research_session_id: str
    intent: str
    tools_used: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    dataset_freshness: Mapping[str, Any]
    groundedness_result: Mapping[str, Any]
    policy_result: Mapping[str, Any]
    missing_data: tuple[str, ...]
    caveats: tuple[str, ...]
    created_at: datetime
    correlation_id: str


__all__ = [
    "MarketRegimeSnapshot",
    "ResearchAnswerAudit",
    "ResearchScenarioPlan",
    "SectorStrengthSnapshot",
    "SetupAnalysis",
    "SetupEvidenceSnapshot",
    "ShortlistCandidate",
    "ShortlistDecisionReport",
    "SymbolLevelSnapshot",
]
