from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

from vnalpha.data_availability.models import EnsureDataAction
from vnalpha.data_availability.planner import EnsureDataSnapshot
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.warehouse.migrations import run_migrations

_REQUIRED_LINEAGE = (
    "as_of_bar_date",
    "scoring_version",
    "feature_build_version",
    "selected_provider",
    "ingestion_run_id",
)


def _eligible_snapshot() -> EnsureDataSnapshot:
    return EnsureDataSnapshot(
        symbol="FPT",
        target_date="2026-07-10",
        lookback_start="2025-05-16",
        symbol_known=True,
        canonical_bars=120,
        benchmark_bars=120,
        feature_snapshot_exists=True,
        candidate_score_exists=True,
        candidate_score_as_of_date="2026-07-10",
        quality_status="pass",
        lineage_fields=frozenset(_REQUIRED_LINEAGE),
    )


def _strict_policy(**overrides) -> DataAvailabilityPolicy:
    values = {
        "auto_sync": False,
        "min_required_bars": 120,
        "require_benchmark_history": True,
        "acceptable_quality_statuses": ("pass",),
        "required_lineage_fields": _REQUIRED_LINEAGE,
    }
    values.update(overrides)
    return DataAvailabilityPolicy(**values)


@pytest.mark.parametrize(
    ("snapshot", "reason", "flag"),
    [
        (
            replace(_eligible_snapshot(), candidate_score_exists=False),
            "score_missing",
            "score_fresh",
        ),
        (
            replace(_eligible_snapshot(), candidate_score_as_of_date="2026-06-01"),
            "score_stale",
            "score_fresh",
        ),
        (
            replace(_eligible_snapshot(), feature_snapshot_exists=False),
            "feature_snapshot_missing",
            "feature_present",
        ),
        (
            replace(_eligible_snapshot(), canonical_bars=119),
            "canonical_history_insufficient",
            "canonical_sufficient",
        ),
        (
            replace(_eligible_snapshot(), benchmark_bars=119),
            "benchmark_history_insufficient",
            "benchmark_sufficient",
        ),
        (
            replace(_eligible_snapshot(), quality_status="fail"),
            "quality_unacceptable",
            "quality_acceptable",
        ),
        (
            replace(
                _eligible_snapshot(),
                lineage_fields=frozenset({"as_of_bar_date"}),
            ),
            "lineage_incomplete",
            "lineage_acceptable",
        ),
    ],
)
def test_cache_policy_rejects_each_incomplete_evidence_class(
    snapshot: EnsureDataSnapshot, reason: str, flag: str
) -> None:
    from vnalpha.data_availability.cache import evaluate_cache_eligibility

    # Given: one supporting cache-evidence class is incomplete.
    # When: the typed cache policy evaluates it.
    eligibility = evaluate_cache_eligibility(snapshot, _strict_policy())

    # Then: the corresponding flag and stable rejection reason identify the gap.
    assert eligibility.eligible is False
    assert reason in eligibility.reasons
    assert getattr(eligibility, flag) is False


def test_cache_policy_accepts_complete_evidence() -> None:
    from vnalpha.data_availability.cache import evaluate_cache_eligibility

    # Given/When: all score, feature, history, quality, and lineage evidence passes.
    eligibility = evaluate_cache_eligibility(_eligible_snapshot(), _strict_policy())

    # Then: the cache is eligible without rejection reasons.
    assert eligibility.eligible is True
    assert eligibility.reasons == ()


def test_cache_policy_can_disable_benchmark_requirement() -> None:
    from vnalpha.data_availability.cache import evaluate_cache_eligibility

    # Given: relative-strength benchmark history is not required by this policy.
    snapshot = replace(_eligible_snapshot(), benchmark_bars=0)

    # When: eligibility is evaluated with that explicit policy.
    eligibility = evaluate_cache_eligibility(
        snapshot,
        _strict_policy(require_benchmark_history=False),
    )

    # Then: absent benchmark history does not reject an otherwise complete cache.
    assert eligibility.eligible is True
    assert eligibility.benchmark_sufficient is True


def _seed_complete_evidence(conn: duckdb.DuckDBPyConnection) -> None:
    date = "2026-07-10"
    conn.execute(
        "INSERT INTO symbol_master (symbol, is_active) VALUES ('FPT', TRUE), "
        "('VNINDEX', TRUE)"
    )
    for symbol in ("FPT", "VNINDEX"):
        conn.execute(
            """
            INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume,
             selected_provider, quality_status, ingestion_run_id)
            VALUES (?, ?, '1D', 10, 11, 9, 10.5, 1000, 'test', 'pass', 'run-1')
            """,
            [symbol, date],
        )
    conn.execute(
        """
        INSERT INTO feature_snapshot
        (symbol, date, close, as_of_bar_date, benchmark_as_of_bar_date,
         source_row_count, benchmark_row_count, feature_data_status,
         feature_build_version, feature_generated_at)
        VALUES ('FPT', ?, 10.5, ?, ?, 1, 1, 'EXACT_DATE', 'test-v1', current_timestamp)
        """,
        [date, date, date],
    )
    lineage = {
        "as_of_bar_date": date,
        "scoring_version": "test-v1",
        "feature_build_version": "test-v1",
        "selected_provider": "test",
        "ingestion_run_id": "run-1",
        "source_quality_status": "pass",
        "lineage_status": "COMPLETE",
    }
    conn.execute(
        """
        INSERT INTO candidate_score
        (symbol, date, score, candidate_class, evidence_json,
         risk_flags_json, lineage_json)
        VALUES ('FPT', ?, 0.75, 'WATCH_CANDIDATE', '{}', '[]', ?)
        """,
        [date, json.dumps(lineage)],
    )


def test_complete_cache_hit_runs_no_provisioning_actions(tmp_path: Path) -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready

    # Given: every required persisted artifact is confirmed and acceptable.
    conn = duckdb.connect()
    run_migrations(conn=conn)
    _seed_complete_evidence(conn)

    def unexpected_action(*_args, **_kwargs):
        raise AssertionError("cache hit must not run provisioning")

    # When: ensure evaluates the complete cache.
    result = ensure_symbol_analysis_ready(
        conn,
        "FPT",
        "2026-07-10",
        policy=_strict_policy(min_required_bars=1),
        _lock_dir=tmp_path,
        _sync_symbols_fn=unexpected_action,
        _sync_ohlcv_fn=unexpected_action,
        _sync_index_fn=unexpected_action,
        _build_canonical_fn=unexpected_action,
        _build_features_fn=unexpected_action,
        _score_universe_fn=unexpected_action,
    )

    # Then: READY is a fast cache hit with no rejection reason or build action.
    assert result.actions_taken == [EnsureDataAction.CACHE_HIT]
    assert result.cache_rejection_reasons == []


def test_cache_rejection_reasons_are_returned_and_observed(tmp_path: Path) -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready

    # Given: a known symbol has none of the required supporting cache evidence.
    conn = duckdb.connect()
    run_migrations(conn=conn)
    conn.execute("INSERT INTO symbol_master (symbol, is_active) VALUES ('FPT', TRUE)")
    events: list[tuple[str, dict | None]] = []

    def capture_event(event_type, *_args, **kwargs):
        events.append((event_type, kwargs.get("extra")))

    # When: ensure rejects the cache before following its no-sync path.
    with patch(
        "vnalpha.data_availability.observability.log_audit",
        side_effect=capture_event,
    ):
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2026-07-10",
            policy=_strict_policy(min_required_bars=1),
            _lock_dir=tmp_path,
        )

    # Then: the result and DATA_ENSURE_CACHE_REJECTED carry stable reasons.
    assert "score_missing" in result.cache_rejection_reasons
    rejected = [
        extra for event, extra in events if event == "DATA_ENSURE_CACHE_REJECTED"
    ]
    assert len(rejected) == 1
    assert rejected[0] is not None
    assert "score_missing" in rejected[0]["reasons"]
