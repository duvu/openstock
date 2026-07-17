from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pytest

from vnalpha.features.build_features import build_features
from vnalpha.features.status import (
    FEATURE_STATUS_CONTRACT_VERSION,
    FeatureDataStatus,
    FeatureExclusionReason,
    parse_feature_eligibility,
    parse_feature_snapshot_eligibility,
)
from vnalpha.observability.context import init_run_context, reset_run_context
from vnalpha.outcomes.models import (
    FORWARD_OUTCOME_MEASUREMENT_CONTRACT_VERSION,
    CandidateOutcomeRecord,
)
from vnalpha.outcomes.repositories import upsert_candidate_outcome
from vnalpha.research_automation.dataset_resolver import DatasetResolver
from vnalpha.research_automation.study_service import ResearchStudyService
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    with in_memory_connection() as connection:
        run_migrations(conn=connection)
        yield connection


@pytest.mark.parametrize(
    ("raw_status", "eligible", "reason"),
    (
        ("EXACT_DATE", True, None),
        ("STALE_DATE", False, FeatureExclusionReason.STALE_FEATURE_DATE),
        ("MISSING_BENCHMARK", False, FeatureExclusionReason.MISSING_BENCHMARK),
        ("good", False, FeatureExclusionReason.UNKNOWN_FEATURE_STATUS),
        (None, False, FeatureExclusionReason.UNKNOWN_FEATURE_STATUS),
    ),
)
def test_feature_status_parser_fails_closed_for_legacy_values(
    raw_status: str | None,
    eligible: bool,
    reason: FeatureExclusionReason | None,
) -> None:
    parsed = parse_feature_eligibility(raw_status)

    assert parsed.eligible is eligible
    assert parsed.exclusion_reason is reason


def test_unversioned_exact_date_snapshot_fails_closed() -> None:
    parsed = parse_feature_snapshot_eligibility("EXACT_DATE", {})

    assert parsed.eligible is False
    assert parsed.exclusion_reason is FeatureExclusionReason.UNKNOWN_FEATURE_STATUS


@pytest.mark.parametrize(
    "lineage",
    (
        '{"feature_status_contract_version":"feature-data-status-v1",'
        '"feature_status_contract_version":"bad"}',
        '{"feature_status_contract_version":"bad",'
        '"feature_status_contract_version":"feature-data-status-v1"}',
    ),
)
def test_duplicate_lineage_contract_keys_fail_closed(
    conn: duckdb.DuckDBPyConnection,
    lineage: str,
) -> None:
    conn.execute(
        "INSERT INTO feature_snapshot "
        "(symbol, date, feature_data_status, lineage_json) "
        "VALUES ('FPT', DATE '2026-07-01', 'EXACT_DATE', ?)",
        [lineage],
    )

    parsed = parse_feature_snapshot_eligibility("EXACT_DATE", lineage)
    resolution = DatasetResolver(conn).resolve_feature_snapshot()

    assert parsed.eligible is False
    assert resolution.dataset.quality_status["eligible_row_count"] == 0
    assert resolution.dataset.quality_status["exclusion_counts"] == {
        FeatureExclusionReason.UNKNOWN_FEATURE_STATUS.value: 1
    }


def test_production_builder_statuses_drive_typed_dataset_eligibility(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    target = date(2026, 5, 1)
    for symbol, first_offset in (("FPT", 119), ("ACB", 120), ("VNINDEX", 119)):
        conn.execute(
            """
            INSERT INTO canonical_ohlcv (
                symbol, interval, time, open, high, low, close, volume,
                selected_provider, quality_status, ingestion_run_id
            )
            SELECT ?, '1D', ?::DATE - (? - i)::INTEGER,
                   100 + i, 101 + i, 99 + i, 100.5 + i, 1000000 + i,
                   'FIXTURE', 'good', 'issue-197-builder'
            FROM range(?) AS bars(i)
            """,
            [symbol, target, first_offset, 120],
        )

    result = build_features(
        conn,
        target.isoformat(),
        universe=["FPT", "ACB"],
    )
    statuses = dict(
        conn.execute(
            "SELECT symbol, feature_data_status FROM feature_snapshot ORDER BY symbol"
        ).fetchall()
    )
    resolution = DatasetResolver(conn).resolve_feature_snapshot()

    assert result == {"built": 2, "skipped": 0}
    assert statuses == {
        "ACB": FeatureDataStatus.STALE_DATE.value,
        "FPT": FeatureDataStatus.EXACT_DATE.value,
    }
    assert resolution.dataset.quality_status["eligible_row_count"] == 1
    assert resolution.dataset.quality_status["exclusion_counts"] == {
        FeatureExclusionReason.STALE_FEATURE_DATE.value: 1
    }


def test_production_builder_emits_missing_benchmark_status(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    target = date(2026, 5, 1)
    conn.execute(
        """
        INSERT INTO canonical_ohlcv (
            symbol, interval, time, open, high, low, close, volume,
            selected_provider, quality_status, ingestion_run_id
        )
        SELECT 'FPT', '1D', ?::DATE - (19 - i)::INTEGER,
               100 + i, 101 + i, 99 + i, 100.5 + i, 1000000 + i,
               'FIXTURE', 'good', 'issue-197-missing-benchmark'
        FROM range(20) AS bars(i)
        """,
        [target],
    )

    result = build_features(conn, target.isoformat(), universe=["FPT"])
    status = conn.execute("SELECT feature_data_status FROM feature_snapshot").fetchone()

    assert result == {"built": 1, "skipped": 0}
    assert status == (FeatureDataStatus.MISSING_BENCHMARK.value,)


def test_hypothesis_reads_complete_later_observations_and_persists_contracts(
    conn: duckdb.DuckDBPyConnection,
    tmp_path: Path,
) -> None:
    reset_run_context()
    _ = init_run_context(surface="test", actor="pytest", log_root=tmp_path)
    try:
        fixtures = (
            ("FPT", "EXACT_DATE", 0.90, 0.10, "COMPLETE"),
            ("VNM", "EXACT_DATE", 0.70, -0.02, "COMPLETE"),
        )
        for symbol, status, trailing_return, forward_return, outcome_status in fixtures:
            conn.execute(
                """
                INSERT INTO feature_snapshot (
                    symbol, date, return_20d, rs_20d_vs_vnindex,
                    feature_data_status, as_of_bar_date, benchmark_as_of_bar_date,
                    lineage_json
                ) VALUES (?, DATE '2026-07-01', ?, 0.05, ?,
                          DATE '2026-07-01', DATE '2026-07-01', ?)
                """,
                [
                    symbol,
                    trailing_return,
                    status,
                    json.dumps(
                        {
                            "feature_status_contract_version": (
                                FEATURE_STATUS_CONTRACT_VERSION
                            )
                        }
                    ),
                ],
            )
            upsert_candidate_outcome(
                conn,
                CandidateOutcomeRecord(
                    symbol=symbol,
                    watchlist_date="2026-07-01",
                    horizon_sessions=20,
                    outcome_status=outcome_status,
                    forward_return=forward_return,
                    price_basis="RAW_UNADJUSTED",
                    benchmark_price_basis="RAW_UNADJUSTED",
                    adjustment_methodology="NONE",
                    adjustment_version="raw-unadjusted-v1",
                    action_overlap_status="CLEAR",
                    scoring_policy_id=BASELINE_SCORING_POLICY.policy_id,
                    scoring_policy_version=BASELINE_SCORING_POLICY.version,
                    scoring_policy_hash=BASELINE_SCORING_POLICY.payload_hash,
                    scoring_policy_status=(
                        BASELINE_SCORING_POLICY.lifecycle_status.value
                    ),
                ),
            )

        outcome = ResearchStudyService(conn).hypothesis(
            "positive rs_20 has better 20-session return"
        )
    finally:
        reset_run_context()

    assert outcome.artifact.metrics["sample_size"] == 2
    assert outcome.artifact.metrics["mean_return_20d"] == pytest.approx(0.04)
    assert outcome.artifact.metrics["excluded_feature_rows"] == 0
    assert outcome.artifact.status.value == "succeeded"
    assert (
        outcome.artifact.lineage["feature_status_contract_version"]
        == FEATURE_STATUS_CONTRACT_VERSION
    )
    assert (
        outcome.artifact.lineage["measurement_contract_version"]
        == FORWARD_OUTCOME_MEASUREMENT_CONTRACT_VERSION
    )
    assert outcome.artifact.lineage["measurement_source"] == (
        "candidate_outcome.forward_return"
    )
    assert outcome.artifact.lineage["measurement_status"] == "COMPLETE"
    assert outcome.artifact.lineage["measurement_horizon_sessions"] == 20
    assert outcome.artifact.lineage["measurement_join_keys"] == [
        "symbol",
        "watchlist_date",
        "horizon_sessions",
    ]


def test_incomplete_and_non_finite_outcomes_are_partial_and_explicit(
    conn: duckdb.DuckDBPyConnection,
    tmp_path: Path,
) -> None:
    current_lineage = json.dumps(
        {"feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION}
    )
    for symbol, lineage in (
        ("FPT", current_lineage),
        ("VNM", current_lineage),
        ("HPG", current_lineage),
        ("ACB", "{}"),
    ):
        conn.execute(
            "INSERT INTO feature_snapshot "
            "(symbol, date, rs_20d_vs_vnindex, feature_data_status, lineage_json) "
            "VALUES (?, DATE '2026-07-01', 0.05, 'EXACT_DATE', ?)",
            [symbol, lineage],
        )
    for symbol, value in (("FPT", 0.1), ("HPG", float("nan")), ("ACB", 9.0)):
        upsert_candidate_outcome(
            conn,
            CandidateOutcomeRecord(
                symbol=symbol,
                watchlist_date="2026-07-01",
                horizon_sessions=20,
                outcome_status="COMPLETE",
                forward_return=value,
                price_basis="RAW_UNADJUSTED",
                benchmark_price_basis="RAW_UNADJUSTED",
                adjustment_methodology="NONE",
                adjustment_version="raw-unadjusted-v1",
                action_overlap_status="CLEAR",
                scoring_policy_id=BASELINE_SCORING_POLICY.policy_id,
                scoring_policy_version=BASELINE_SCORING_POLICY.version,
                scoring_policy_hash=BASELINE_SCORING_POLICY.payload_hash,
                scoring_policy_status=BASELINE_SCORING_POLICY.lifecycle_status.value,
            ),
        )
    reset_run_context()
    _ = init_run_context(surface="test", actor="pytest", log_root=tmp_path)
    try:
        outcome = ResearchStudyService(conn).hypothesis(
            "positive rs_20 has better 20-session return"
        )
    finally:
        reset_run_context()

    assert outcome.artifact.status.value == "rejected"
    assert outcome.artifact.metrics["sample_size"] == 1
    assert outcome.artifact.metrics["missing_observation_rows"] == 2
    assert outcome.artifact.metrics["excluded_feature_rows"] == 1
    assert outcome.artifact.lineage["measurement_status"] == "PARTIAL"
    assert any(
        "no complete later observation" in item for item in outcome.artifact.caveats
    )
    validation = json.loads(
        outcome.artifact.outputs.validation_json.read_text(encoding="utf-8")
    )
    assert validation["sample_size"] == 1


def test_event_study_excludes_overflowed_forward_return(
    conn: duckdb.DuckDBPyConnection,
    tmp_path: Path,
) -> None:
    lineage = json.dumps(
        {"feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION}
    )
    conn.execute(
        "INSERT INTO feature_snapshot "
        "(symbol, date, rs_20d_vs_vnindex, feature_data_status, "
        "as_of_bar_date, benchmark_as_of_bar_date, lineage_json) "
        "VALUES ('FPT', DATE '2026-07-01', 0.05, 'EXACT_DATE', "
        "DATE '2026-07-01', DATE '2026-07-01', ?)",
        [lineage],
    )
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, quality_status) VALUES "
        "('FPT', DATE '2026-07-01', '1D', 1e-308, 'pass'), "
        "('FPT', DATE '2026-07-02', '1D', 1e308, 'pass')"
    )
    reset_run_context()
    _ = init_run_context(surface="test", actor="pytest", log_root=tmp_path)
    try:
        outcome = ResearchStudyService(conn).event_study(
            "rs_20d_vs_vnindex > 0",
            horizon=1,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
        )
    finally:
        reset_run_context()

    assert outcome.artifact.metrics["sample_size"] == 0
    assert outcome.rows[0][4] == "invalid_outcome"


@pytest.mark.parametrize(
    ("outcome_basis", "affected_range", "expected_status"),
    [
        ("ADJUSTED", False, "mixed_price_basis"),
        ("RAW_UNADJUSTED", True, "corporate_action_overlap"),
    ],
)
def test_event_study_rejects_untrustworthy_price_basis(
    conn: duckdb.DuckDBPyConnection,
    tmp_path: Path,
    outcome_basis: str,
    affected_range: bool,
    expected_status: str,
) -> None:
    lineage = json.dumps(
        {"feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION}
    )
    conn.execute(
        "INSERT INTO feature_snapshot "
        "(symbol, date, rs_20d_vs_vnindex, feature_data_status, "
        "as_of_bar_date, benchmark_as_of_bar_date, lineage_json) "
        "VALUES ('FPT', DATE '2026-07-01', 0.05, 'EXACT_DATE', "
        "DATE '2026-07-01', DATE '2026-07-01', ?)",
        [lineage],
    )
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, quality_status, price_basis) VALUES "
        "('FPT', DATE '2026-07-01', '1D', 100.0, 'pass', 'RAW_UNADJUSTED'), "
        "('FPT', DATE '2026-07-02', '1D', 110.0, 'pass', ?)",
        [outcome_basis],
    )
    if affected_range:
        conn.execute(
            "INSERT INTO corporate_action_affected_range "
            "(signal_id, action_id, revision_id, symbol, affected_from_date, "
            "affected_to_date, reason) VALUES "
            "('signal-event', 'action-event', 'revision-event', 'FPT', "
            "'2026-07-02', '2026-07-02', 'REVISED_ACTION')"
        )
    reset_run_context()
    _ = init_run_context(surface="test", actor="pytest", log_root=tmp_path)
    try:
        outcome = ResearchStudyService(conn).event_study(
            "rs_20d_vs_vnindex > 0",
            horizon=1,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
        )
    finally:
        reset_run_context()

    assert outcome.artifact.metrics["sample_size"] == 0
    assert outcome.rows[0][4] == expected_status
