from __future__ import annotations

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
)
from vnalpha.observability.context import init_run_context, reset_run_context
from vnalpha.outcomes.models import (
    FORWARD_OUTCOME_MEASUREMENT_CONTRACT_VERSION,
    CandidateOutcomeRecord,
)
from vnalpha.outcomes.repositories import upsert_candidate_outcome
from vnalpha.research_automation.dataset_resolver import DatasetResolver
from vnalpha.research_automation.study_service import ResearchStudyService
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
            ("ACB", "good", 5.00, 4.00, "COMPLETE"),
        )
        for symbol, status, trailing_return, forward_return, outcome_status in fixtures:
            conn.execute(
                """
                INSERT INTO feature_snapshot (
                    symbol, date, return_20d, rs_20d_vs_vnindex,
                    feature_data_status, as_of_bar_date, benchmark_as_of_bar_date
                ) VALUES (?, DATE '2026-07-01', ?, 0.05, ?,
                          DATE '2026-07-01', DATE '2026-07-01')
                """,
                [symbol, trailing_return, status],
            )
            upsert_candidate_outcome(
                conn,
                CandidateOutcomeRecord(
                    symbol=symbol,
                    watchlist_date="2026-07-01",
                    horizon_sessions=20,
                    outcome_status=outcome_status,
                    forward_return=forward_return,
                ),
            )

        outcome = ResearchStudyService(conn).hypothesis(
            "positive rs_20 has better 20-session return"
        )
    finally:
        reset_run_context()

    assert outcome.artifact.metrics["sample_size"] == 2
    assert outcome.artifact.metrics["mean_return_20d"] == pytest.approx(0.04)
    assert outcome.artifact.metrics["excluded_feature_rows"] == 1
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
