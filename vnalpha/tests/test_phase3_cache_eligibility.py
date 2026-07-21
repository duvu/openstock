from __future__ import annotations

import json
from pathlib import Path

import duckdb

from vnalpha.data_availability.models import EnsureDataAction
from vnalpha.data_availability.planner import EnsureDataSnapshot
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.features.status import FEATURE_STATUS_CONTRACT_VERSION
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


def _seed_complete_evidence(conn: duckdb.DuckDBPyConnection) -> None:
    date = "2026-07-10"
    feature_lineage = json.dumps(
        {
            "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
            "benchmark_symbol": "VNINDEX",
            "selected_provider": "test",
            "ingestion_run_id": "run-1",
        }
    )
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
         feature_build_version, feature_generated_at, feature_profile,
         neutral_completeness, relative_strength_completeness,
         required_bar_count, observed_bar_count, feature_completeness_rule_version,
         lineage_json)
        VALUES ('FPT', ?, 10.5, ?, ?, 120, 120, 'EXACT_DATE', 'test-v1', current_timestamp,
                'STANDARD_120', 'COMPLETE', 'COMPLETE', 120, 120,
                'feature-completeness-v1', ?)
        """,
        [date, date, date, feature_lineage],
    )
    conn.executemany(
        "INSERT INTO relative_strength_snapshot "
        "(symbol, date, benchmark_symbol, horizon_sessions, relative_return, "
        "source_bar_date, benchmark_bar_date, source_row_count, "
        "benchmark_row_count, data_status, methodology_version, generated_at, "
        "lineage_json) VALUES ('FPT', ?, 'VNINDEX', ?, 0.1, ?, ?, 120, 120, "
        "'SUCCESS', 'test-v1', current_timestamp, ?)",
        [[date, horizon, date, date, feature_lineage] for horizon in (20, 60)],
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
