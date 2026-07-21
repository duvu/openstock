"""Tests for data_availability.checks — read-only warehouse queries."""

from __future__ import annotations

import json

import duckdb

from vnalpha.features.status import FEATURE_STATUS_CONTRACT_VERSION
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.migrations import run_migrations


def _fresh_conn():
    conn = duckdb.connect()
    run_migrations(conn=conn)
    return conn


def _insert_symbol(conn, symbol="FPT"):
    conn.execute(
        "INSERT INTO symbol_master (symbol, is_active, last_seen_at) VALUES (?, TRUE, current_timestamp)",
        [symbol],
    )


def _insert_canonical_bar(conn, symbol, date_str, interval="1D"):
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
        (symbol, time, interval, open, high, low, close, volume, selected_provider, quality_status)
        VALUES (?, ?, ?, 100, 110, 90, 105, 1000000, 'test', 'pass')
        """,
        [symbol, date_str, interval],
    )


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
    import json

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


class TestGetSymbolMasterStatus:
    def test_symbol_exists(self):
        from vnalpha.data_availability.checks import get_symbol_master_status

        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")
        assert get_symbol_master_status(conn, "FPT") is True
