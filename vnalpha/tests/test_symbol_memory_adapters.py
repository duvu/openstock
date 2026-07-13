from __future__ import annotations

from datetime import date, datetime, timezone

from vnalpha.research_models.models import (
    MarketRegimeSnapshot,
    SetupAnalysis,
    SymbolLevelSnapshot,
)
from vnalpha.symbol_memory.adapters import (
    CandidateScoreSnapshot,
    FeatureSnapshot,
    candidate_score_evidence,
    feature_snapshot_evidence,
    market_regime_evidence,
    setup_analysis_evidence,
    symbol_level_evidence,
)


def test_persisted_candidate_and_feature_snapshots_create_grounded_evidence() -> None:
    timestamp = datetime(2026, 7, 13, tzinfo=timezone.utc)
    candidate = candidate_score_evidence(
        CandidateScoreSnapshot(
            symbol="fpt",
            as_of_date=date(2026, 7, 13),
            score=0.82,
            candidate_class="watch",
            setup_type="base",
            correlation_id="candidate-001",
            persisted_at=timestamp,
        )
    )
    feature = feature_snapshot_evidence(
        FeatureSnapshot(
            symbol="FPT",
            as_of_date=date(2026, 7, 13),
            quality_status="validated",
            source_ref="feature_snapshot:FPT:2026-07-13",
            correlation_id="feature-001",
            persisted_at=timestamp,
        )
    )

    assert candidate.source_ref == "candidate_score:FPT:2026-07-13"
    assert candidate.value["unit"] == "score"
    assert feature.claim_type == "data_quality_caveat"


def test_validated_research_models_map_to_symbol_grounded_evidence() -> None:
    timestamp = datetime(2026, 7, 13, tzinfo=timezone.utc)
    regime = market_regime_evidence(
        "FPT",
        MarketRegimeSnapshot(
            market_regime_snapshot_id="regime-001",
            as_of_date=date(2026, 7, 13),
            regime_state="risk_on",
            index_trend="up",
            index_volatility="normal",
            breadth_summary={},
            sector_strength_ref=None,
            freshness="fresh",
            lineage={},
            methodology_version="v1",
            correlation_id="regime-correlation",
            quality_status="validated",
            caveats=(),
            created_at=timestamp,
        ),
    )
    levels = symbol_level_evidence(
        SymbolLevelSnapshot(
            symbol_level_snapshot_id="levels-001",
            symbol="FPT",
            as_of_date=date(2026, 7, 13),
            support_levels=(100.0,),
            resistance_levels=(110.0,),
            pivot_levels=(),
            level_strength={},
            source_bar_refs=("bars:FPT:2026-07-13",),
            freshness="fresh",
            lineage={},
            methodology_version="v1",
            correlation_id="levels-correlation",
            quality_status="validated",
            caveats=(),
            created_at=timestamp,
        )
    )
    setup = setup_analysis_evidence(
        SetupAnalysis(
            setup_analysis_id="setup-001",
            symbol="FPT",
            as_of_date=date(2026, 7, 13),
            setup_type="base",
            setup_quality="high",
            trend_context="up",
            momentum_context="improving",
            relative_strength_context="improving",
            volume_context="normal",
            volatility_context="contracting",
            level_snapshot_ref="levels-001",
            confidence=0.8,
            freshness="fresh",
            lineage={},
            methodology_version="v1",
            correlation_id="setup-correlation",
            quality_status="validated",
            caveats=(),
            created_at=timestamp,
        )
    )

    assert regime.symbol == "FPT"
    assert levels.source_ref == "research_symbol_level_snapshot:levels-001"
    assert setup.claim_type == "technical_observation"
