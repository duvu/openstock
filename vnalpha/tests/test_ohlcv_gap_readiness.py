from vnalpha.data_availability.cache import evaluate_cache_eligibility
from vnalpha.data_availability.models import EvidenceIssue
from vnalpha.data_availability.planner import (
    EnsureDataSnapshot,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy


def test_unresolved_true_gap_blocks_readiness_even_when_bar_counts_are_sufficient() -> (
    None
):
    # Given
    snapshot = EnsureDataSnapshot(
        symbol="FPT",
        target_date="2026-09-02",
        lookback_start="2026-09-01",
        symbol_known=True,
        canonical_bars=2,
        benchmark_bars=2,
        feature_snapshot_exists=True,
        candidate_score_exists=True,
        candidate_score_as_of_date="2026-09-02",
        quality_status="pass",
        lineage_fields=frozenset(
            {
                "as_of_bar_date",
                "feature_build_version",
                "ingestion_run_id",
                "scoring_version",
                "selected_provider",
            }
        ),
        unresolved_true_gap_count=1,
    )

    # When
    eligibility = evaluate_cache_eligibility(
        snapshot,
        DataAvailabilityPolicy(min_required_bars=2),
    )

    # Then
    assert eligibility.eligible is False
    assert EvidenceIssue.CANONICAL_GAPS_UNRESOLVED in eligibility.issues
