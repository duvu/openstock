from __future__ import annotations

from datetime import date, datetime, timezone

from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.symbol_memory.adapters import (
    CandidateScoreSnapshot,
    FeatureSnapshot,
    candidate_score_evidence,
    feature_snapshot_evidence,
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
