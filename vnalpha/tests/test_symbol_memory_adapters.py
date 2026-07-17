from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from vnalpha.research_automation.models import (
    ArtifactOutputs,
    DatasetRef,
    ResearchArtifact,
    ResearchArtifactStatus,
    ResearchArtifactType,
)
from vnalpha.research_models.models import (
    MarketRegimeSnapshot,
    SetupAnalysis,
    SymbolLevelSnapshot,
)
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
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
            scoring_policy_id=BASELINE_SCORING_POLICY.policy_id,
            scoring_policy_hash=BASELINE_SCORING_POLICY.payload_hash,
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


def test_research_automation_adapter_accepts_validated_artifacts_only() -> None:
    timestamp = datetime(2026, 7, 13, tzinfo=timezone.utc)
    artifact = ResearchArtifact(
        artifact_id="artifact-001",
        artifact_type=ResearchArtifactType.HYPOTHESIS_TEST,
        name="hypothesis-test",
        purpose="Validate a research hypothesis.",
        created_at=timestamp,
        created_by="test",
        correlation_id="artifact-correlation",
        status=ResearchArtifactStatus.VALIDATED,
        input_datasets=(
            DatasetRef(
                dataset_name="daily_bars",
                snapshot_id="snapshot-001",
                symbols=("FPT",),
                end_date=date(2026, 7, 13),
            ),
        ),
        sandbox_job_id=None,
        parameters={},
        metrics={},
        lineage={"computation": "approved_deterministic_tool"},
        quality_status={"state": "validated"},
        caveats=("Sample size is limited.",),
        outputs=ArtifactOutputs(
            manifest=Path("manifest.json"),
            result_json=Path("result.json"),
            summary_md=Path("summary.md"),
            lineage_json=Path("lineage.json"),
            validation_json=Path("validation.json"),
        ),
    )

    from vnalpha.symbol_memory.adapters import research_automation_evidence

    evidence = research_automation_evidence("FPT", artifact)

    assert evidence.source_ref == "research_automation:artifact-001"
    assert evidence.as_of_date == date(2026, 7, 13)
    assert evidence.value["validation_status"] == "validated"

    with pytest.raises(ValueError, match="validated"):
        research_automation_evidence(
            "FPT",
            replace(artifact, status=ResearchArtifactStatus.SUCCEEDED),
        )
