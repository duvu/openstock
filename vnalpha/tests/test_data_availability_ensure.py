"""Tests for data_availability.ensure — full pipeline with dependency injection."""

from __future__ import annotations

import json

import duckdb

from vnalpha.features.status import FEATURE_STATUS_CONTRACT_VERSION
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    insert_raw_ohlcv,
)


def _fresh_conn():
    conn = duckdb.connect()
    run_migrations(conn=conn)
    return conn


def _insert_symbol(conn, symbol="FPT"):
    conn.execute(
        "INSERT INTO symbol_master (symbol, is_active, last_seen_at) VALUES (?, TRUE, current_timestamp)",
        [symbol],
    )


def _insert_canonical_bars(conn, symbol, dates, interval="1D"):
    for d in dates:
        conn.execute(
            """
            INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume, selected_provider, quality_status)
            VALUES (?, ?, ?, 100, 110, 90, 105, 1000000, 'test', 'pass')
            """,
            [symbol, d, interval],
        )


def _insert_raw_bars(conn, symbol, dates):
    run_id = create_ingestion_run(conn, "test", f"/test/{symbol.lower()}")
    insert_raw_ohlcv(
        conn,
        run_id,
        symbol,
        [
            {
                "time": value,
                "interval": "1D",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1_000_000.0,
            }
            for value in dates
        ],
        provider="test",
        quality_status="pass",
    )
    finish_ingestion_run(conn, run_id, status="SUCCESS")


def _insert_feature_snapshot(conn, symbol, date_str):
    lineage = json.dumps(
        {
            "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
            "benchmark_symbol": "VNINDEX",
            "selected_provider": "test",
            "ingestion_run_id": "test-run",
        }
    )
    conn.execute(
        """
        INSERT INTO feature_snapshot
        (symbol, date, close, ma20, as_of_bar_date, feature_data_status,
         feature_build_version, feature_generated_at, feature_profile,
         neutral_completeness, relative_strength_completeness,
         required_bar_count, observed_bar_count, feature_completeness_rule_version,
         lineage_json)
        VALUES (?, ?, 105.0, 100.0, ?, 'EXACT_DATE', 'dev', current_timestamp,
                'STANDARD_120', 'COMPLETE', 'COMPLETE', 120, 120,
                'feature-completeness-v1', ?)
        """,
        [symbol, date_str, date_str, lineage],
    )
    conn.executemany(
        "INSERT INTO relative_strength_snapshot "
        "(symbol, date, benchmark_symbol, horizon_sessions, relative_return, "
        "source_bar_date, benchmark_bar_date, source_row_count, "
        "benchmark_row_count, data_status, methodology_version, generated_at, "
        "lineage_json) VALUES (?, ?, 'VNINDEX', ?, 0.1, ?, ?, 120, 120, "
        "'SUCCESS', 'test-v1', current_timestamp, ?)",
        [
            [symbol, date_str, horizon, date_str, date_str, lineage]
            for horizon in (20, 60)
        ],
    )


def _insert_candidate_score(conn, symbol, date_str, as_of_bar_date=None):
    lineage = {
        "as_of_bar_date": as_of_bar_date or date_str,
        "scoring_version": "test-v1",
        "feature_build_version": "test-v1",
        "selected_provider": "test",
        "ingestion_run_id": "test-run",
        "source_quality_status": "pass",
        "lineage_status": "COMPLETE",
        "scoring_policy_id": BASELINE_SCORING_POLICY.policy_id,
        "scoring_policy_version": BASELINE_SCORING_POLICY.version,
        "scoring_policy_hash": BASELINE_SCORING_POLICY.payload_hash,
        "scoring_policy_status": BASELINE_SCORING_POLICY.lifecycle_status.value,
    }
    conn.execute(
        """
        INSERT INTO candidate_score
        (symbol, date, score, candidate_class, setup_type,
         trend_score, relative_strength_score, volume_score,
         base_score, breakout_score, risk_quality_score,
         evidence_json, risk_flags_json, lineage_json,
         scoring_policy_id, scoring_policy_version,
         scoring_policy_hash, scoring_policy_status)
        VALUES (?, ?, 0.75, 'STRONG_CANDIDATE', 'MOMENTUM_CONTINUATION',
                0.8, 0.7, 0.6, 0.5, 0.4, 0.9, '{}', '[]', ?, ?, ?, ?, ?)
        """,
        [
            symbol,
            date_str,
            json.dumps(lineage),
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )


# DI no-op stubs
def _noop_sync_symbols(conn, **kwargs):
    return {"total": 0, "inserted": 0}


def _noop_sync_ohlcv(conn, universe, start, end, **kwargs):
    return {"inserted": 0, "skipped": 0}


def _noop_sync_index(conn, symbol, start, end, **kwargs):
    return {"inserted": 0}


def _noop_build_canonical(conn, symbol, **kwargs):
    return {"upserted": 0, "rejected": 0}


def _noop_build_features(conn, target_date, universe, benchmark_symbol, **kwargs):
    return {"built": 0, "skipped": 0}


def _noop_score_universe(conn, date, universe, **kwargs):
    return 0


class TestCacheHit:
    """If candidate_score is fresh, return READY immediately without syncing."""

    def test_returns_ready_on_complete_cache_hit(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.models import EnsureDataStatus
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        conn = _fresh_conn()
        date = "2025-06-30"
        _insert_symbol(conn, "FPT")
        _insert_symbol(conn, "VNINDEX")
        _insert_canonical_bars(conn, "FPT", [date])
        _insert_canonical_bars(conn, "VNINDEX", [date])
        _insert_feature_snapshot(conn, "FPT", date)
        _insert_candidate_score(conn, "FPT", date, as_of_bar_date=date)

        policy = DataAvailabilityPolicy(auto_sync=True, min_required_bars=1)
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            date,
            policy=policy,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _sync_index_fn=_noop_sync_index,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert result.status == EnsureDataStatus.READY
