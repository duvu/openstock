from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from vnalpha.research_automation.models import (
    ResearchArtifact,
    ResearchArtifactStatus,
)
from vnalpha.research_models.models import (
    MarketRegimeSnapshot,
    SetupAnalysis,
    SymbolLevelSnapshot,
)
from vnalpha.symbol_memory.context_snapshots import (
    CanonicalOhlcvBasisSnapshot,
    SymbolIdentitySnapshot,
    canonical_ohlcv_basis_value,
    symbol_identity_value,
)
from vnalpha.symbol_memory.ingestion import MemoryEvidence
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.warehouse.symbol_lifecycle import SymbolTaxonomyAsOf


@dataclass(frozen=True, slots=True)
class CandidateScoreSnapshot:
    symbol: str
    as_of_date: date
    score: float
    candidate_class: str
    setup_type: str | None
    correlation_id: str
    persisted_at: datetime
    scoring_policy_id: str
    scoring_policy_hash: str


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    symbol: str
    as_of_date: date
    quality_status: str
    source_ref: str
    correlation_id: str
    persisted_at: datetime


@dataclass(frozen=True, slots=True)
class CandidateStateSnapshot:
    symbol: str
    as_of_date: date
    candidate_class: str
    setup_type: str | None
    risk_flags: tuple[str, ...]
    correlation_id: str
    persisted_at: datetime
    scoring_policy_id: str
    scoring_policy_hash: str


def candidate_score_evidence(snapshot: CandidateScoreSnapshot) -> MemoryEvidence:
    symbol = normalize_symbol(snapshot.symbol)
    value = {
        "value": snapshot.score,
        "unit": "score",
        "meaning": "persisted composite candidate score",
        "candidate_class": snapshot.candidate_class,
        "setup_type": snapshot.setup_type,
    }
    value["scoring_policy_id"] = snapshot.scoring_policy_id
    value["scoring_policy_hash"] = snapshot.scoring_policy_hash
    return MemoryEvidence(
        symbol=symbol,
        claim_type="candidate_score",
        predicate="composite_score",
        value=value,
        source_ref=f"candidate_score:{symbol}:{snapshot.as_of_date.isoformat()}",
        observed_at=snapshot.persisted_at,
        as_of_date=snapshot.as_of_date,
        confidence=snapshot.score,
        correlation_id=snapshot.correlation_id,
        source_published_at=snapshot.as_of_date,
    )


def candidate_state_evidence(snapshot: CandidateStateSnapshot) -> MemoryEvidence:
    symbol = normalize_symbol(snapshot.symbol)
    return MemoryEvidence(
        symbol=symbol,
        claim_type="candidate_state",
        predicate="candidate_classification",
        value={
            "candidate_class": snapshot.candidate_class,
            "setup_type": snapshot.setup_type,
            "risk_flags": list(snapshot.risk_flags),
            "scoring_policy_id": snapshot.scoring_policy_id,
            "scoring_policy_hash": snapshot.scoring_policy_hash,
        },
        source_ref=f"candidate_score:{symbol}:{snapshot.as_of_date.isoformat()}",
        observed_at=snapshot.persisted_at,
        as_of_date=snapshot.as_of_date,
        confidence=None,
        correlation_id=snapshot.correlation_id,
        source_published_at=snapshot.as_of_date,
    )


def taxonomy_identity_evidence(
    taxonomy: SymbolTaxonomyAsOf,
    *,
    correlation_id: str,
    observed_at: datetime,
    as_of_date: date,
) -> MemoryEvidence:
    return MemoryEvidence(
        symbol=normalize_symbol(taxonomy.symbol),
        claim_type="symbol_identity",
        predicate="taxonomy_identity",
        value=taxonomy_identity_value(taxonomy),
        source_ref=f"symbol_identity:{taxonomy.symbol}:{as_of_date.isoformat()}",
        observed_at=observed_at,
        as_of_date=as_of_date,
        confidence=None,
        correlation_id=correlation_id,
        source_published_at=as_of_date,
    )


def taxonomy_identity_value(taxonomy: SymbolTaxonomyAsOf) -> dict[str, Any]:
    return {
        "exchange": taxonomy.exchange,
        "security_type": taxonomy.security_type,
        "lifecycle_status": taxonomy.lifecycle_status,
        "sector_code": taxonomy.sector_code,
        "sector_name": taxonomy.sector_name,
        "industry_code": taxonomy.industry_code,
        "industry_name": taxonomy.industry_name,
        "taxonomy_name": taxonomy.taxonomy_name,
        "taxonomy_version": taxonomy.taxonomy_version,
        "source_snapshot_id": taxonomy.source_snapshot_id,
    }


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
        source_published_at=snapshot.as_of_date,
    )


def symbol_identity_evidence(
    snapshot: SymbolIdentitySnapshot,
    *,
    correlation_id: str,
    observed_at: datetime,
    as_of_date: date,
) -> MemoryEvidence:
    return MemoryEvidence(
        symbol=normalize_symbol(snapshot.symbol),
        claim_type="symbol_identity",
        predicate="security_identity",
        value=symbol_identity_value(snapshot),
        source_ref=f"symbol_identity:{snapshot.symbol}:{as_of_date.isoformat()}",
        observed_at=observed_at,
        as_of_date=as_of_date,
        confidence=None,
        correlation_id=correlation_id,
        source_published_at=as_of_date,
    )


def canonical_ohlcv_basis_evidence(
    snapshot: CanonicalOhlcvBasisSnapshot,
    *,
    correlation_id: str,
    observed_at: datetime,
    as_of_date: date,
) -> MemoryEvidence:
    return MemoryEvidence(
        symbol=normalize_symbol(snapshot.symbol),
        claim_type="data_readiness",
        predicate="canonical_ohlcv_basis",
        value=canonical_ohlcv_basis_value(snapshot),
        source_ref=f"canonical_ohlcv:{snapshot.symbol}:{as_of_date.isoformat()}",
        observed_at=observed_at,
        as_of_date=as_of_date,
        confidence=None,
        correlation_id=correlation_id,
        source_published_at=as_of_date,
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
            f"research_market_regime_snapshot:{snapshot.market_regime_snapshot_id}"
        ),
        observed_at=snapshot.created_at,
        as_of_date=snapshot.as_of_date,
        confidence=None,
        correlation_id=snapshot.correlation_id,
        source_published_at=snapshot.as_of_date,
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
            "unit": "price",
            "meaning": "persisted symbol levels",
        },
        source_ref=(
            f"research_symbol_level_snapshot:{snapshot.symbol_level_snapshot_id}"
        ),
        observed_at=snapshot.created_at,
        as_of_date=snapshot.as_of_date,
        confidence=None,
        correlation_id=snapshot.correlation_id,
        source_published_at=snapshot.as_of_date,
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
        source_published_at=snapshot.as_of_date,
    )


def research_automation_evidence(
    symbol: str, artifact: ResearchArtifact
) -> MemoryEvidence:
    canonical_symbol = normalize_symbol(symbol)
    if artifact.status not in {
        ResearchArtifactStatus.VALIDATED,
        ResearchArtifactStatus.PROMOTED,
    }:
        raise ValueError(
            "Research automation artifacts must be validated to enter memory."
        )
    if not any(
        canonical_symbol in dataset.symbols for dataset in artifact.input_datasets
    ):
        raise ValueError(
            "Research automation artifact does not contain the requested symbol."
        )
    as_of_date = max(
        (
            dataset.end_date or dataset.start_date or artifact.created_at.date()
            for dataset in artifact.input_datasets
        ),
        default=artifact.created_at.date(),
    )
    return MemoryEvidence(
        symbol=canonical_symbol,
        claim_type="research_automation_artifact",
        predicate="validated_research_artifact",
        value={
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type.value,
            "validation_status": artifact.status.value,
            "caveats": artifact.caveats,
        },
        source_ref=f"research_automation:{artifact.artifact_id}",
        observed_at=artifact.created_at,
        as_of_date=as_of_date,
        confidence=None,
        correlation_id=artifact.correlation_id,
        source_published_at=as_of_date,
    )


__all__ = [
    "CandidateScoreSnapshot",
    "CandidateStateSnapshot",
    "CanonicalOhlcvBasisSnapshot",
    "FeatureSnapshot",
    "SymbolIdentitySnapshot",
    "canonical_ohlcv_basis_evidence",
    "candidate_score_evidence",
    "candidate_state_evidence",
    "feature_snapshot_evidence",
    "market_regime_evidence",
    "research_automation_evidence",
    "setup_analysis_evidence",
    "symbol_identity_evidence",
    "symbol_level_evidence",
    "taxonomy_identity_evidence",
    "taxonomy_identity_value",
]
