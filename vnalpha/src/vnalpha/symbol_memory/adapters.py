from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from vnalpha.research_models.models import (
    MarketRegimeSnapshot,
    SetupAnalysis,
    SymbolLevelSnapshot,
)
from vnalpha.symbol_memory.ingestion import MemoryEvidence
from vnalpha.symbol_memory.paths import normalize_symbol


@dataclass(frozen=True, slots=True)
class CandidateScoreSnapshot:
    symbol: str
    as_of_date: date
    score: float
    candidate_class: str
    setup_type: str | None
    correlation_id: str
    persisted_at: datetime


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    symbol: str
    as_of_date: date
    quality_status: str
    source_ref: str
    correlation_id: str
    persisted_at: datetime


def candidate_score_evidence(snapshot: CandidateScoreSnapshot) -> MemoryEvidence:
    symbol = normalize_symbol(snapshot.symbol)
    return MemoryEvidence(
        symbol=symbol,
        claim_type="candidate_score",
        predicate="composite_score",
        value={
            "value": snapshot.score,
            "unit": "score",
            "meaning": "persisted composite candidate score",
            "candidate_class": snapshot.candidate_class,
            "setup_type": snapshot.setup_type,
        },
        source_ref=f"candidate_score:{symbol}:{snapshot.as_of_date.isoformat()}",
        observed_at=snapshot.persisted_at,
        as_of_date=snapshot.as_of_date,
        confidence=snapshot.score,
        correlation_id=snapshot.correlation_id,
    )


def feature_snapshot_evidence(snapshot: FeatureSnapshot) -> MemoryEvidence:
    return MemoryEvidence(
        symbol=normalize_symbol(snapshot.symbol),
        claim_type="data_quality_caveat",
        predicate="feature_data_quality",
        value={"status": snapshot.quality_status},
        source_ref=snapshot.source_ref,
        observed_at=snapshot.persisted_at,
        as_of_date=snapshot.as_of_date,
        confidence=None,
        correlation_id=snapshot.correlation_id,
    )


def market_regime_evidence(
    symbol: str, snapshot: MarketRegimeSnapshot
) -> MemoryEvidence:
    return MemoryEvidence(
        symbol=normalize_symbol(symbol),
        claim_type="market_or_sector_context",
        predicate="market_regime",
        value={
            "regime_state": snapshot.regime_state,
            "index_trend": snapshot.index_trend,
            "index_volatility": snapshot.index_volatility,
        },
        source_ref=(
            "research_market_regime_snapshot:"
            f"{snapshot.market_regime_snapshot_id}"
        ),
        observed_at=snapshot.created_at,
        as_of_date=snapshot.as_of_date,
        confidence=None,
        correlation_id=snapshot.correlation_id,
    )


def symbol_level_evidence(snapshot: SymbolLevelSnapshot) -> MemoryEvidence:
    return MemoryEvidence(
        symbol=normalize_symbol(snapshot.symbol),
        claim_type="technical_observation",
        predicate="symbol_levels",
        value={
            "support_levels": snapshot.support_levels,
            "resistance_levels": snapshot.resistance_levels,
            "pivot_levels": snapshot.pivot_levels,
            "meaning": "persisted symbol levels",
        },
        source_ref=(
            "research_symbol_level_snapshot:"
            f"{snapshot.symbol_level_snapshot_id}"
        ),
        observed_at=snapshot.created_at,
        as_of_date=snapshot.as_of_date,
        confidence=None,
        correlation_id=snapshot.correlation_id,
    )


def setup_analysis_evidence(snapshot: SetupAnalysis) -> MemoryEvidence:
    return MemoryEvidence(
        symbol=normalize_symbol(snapshot.symbol),
        claim_type="technical_observation",
        predicate="setup_analysis",
        value={
            "setup_type": snapshot.setup_type,
            "setup_quality": snapshot.setup_quality,
            "trend_context": snapshot.trend_context,
            "confidence": snapshot.confidence,
            "unit": "probability",
            "meaning": "validated persisted setup analysis confidence",
        },
        source_ref=f"research_setup_analysis:{snapshot.setup_analysis_id}",
        observed_at=snapshot.created_at,
        as_of_date=snapshot.as_of_date,
        confidence=snapshot.confidence,
        correlation_id=snapshot.correlation_id,
    )


__all__ = [
    "CandidateScoreSnapshot",
    "FeatureSnapshot",
    "candidate_score_evidence",
    "feature_snapshot_evidence",
    "market_regime_evidence",
    "setup_analysis_evidence",
    "symbol_level_evidence",
]
