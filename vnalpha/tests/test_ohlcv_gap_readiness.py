import duckdb

from vnalpha.data_availability.cache import evaluate_cache_eligibility
from vnalpha.data_availability.models import EvidenceIssue
from vnalpha.data_availability.planner import (
    EnsureDataSnapshot,
    capture_availability_snapshot,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.warehouse.migrations import run_migrations


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


def test_snapshot_exposes_persisted_unresolved_true_gap_as_canonical_evidence() -> None:
    # Given
    conn = duckdb.connect()
    run_migrations(conn=conn)
    conn.execute(
        """
        INSERT INTO ohlcv_gap_observation
            (symbol, interval, session_date, gap_kind, calendar_version,
             first_observed_at, last_observed_at, correlation_id)
        VALUES ('FPT', '1D', '2026-09-02', 'TRUE_GAP', 'vn-session-v1',
                current_timestamp, current_timestamp, 'corr-readiness')
        """
    )

    # When
    snapshot = capture_availability_snapshot(
        conn,
        "FPT",
        "2026-09-02",
        DataAvailabilityPolicy(min_required_bars=1),
    )

    # Then
    canonical_evidence = next(
        evidence
        for evidence in snapshot.artifact_evidence
        if evidence.artifact.value == "canonical_ohlcv"
    )
    assert snapshot.unresolved_true_gap_count == 1
    assert EvidenceIssue.CANONICAL_GAPS_UNRESOLVED in canonical_evidence.issues
