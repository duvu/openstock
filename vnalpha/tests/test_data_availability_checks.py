"""Tests for data_availability.checks — read-only warehouse queries."""

from __future__ import annotations

import duckdb
import pytest

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
    conn.execute(
        """
        INSERT INTO feature_snapshot
        (symbol, date, close, ma20, as_of_bar_date, feature_data_status,
         feature_build_version, feature_generated_at, feature_profile,
         neutral_completeness, relative_strength_completeness,
         required_bar_count, observed_bar_count, feature_completeness_rule_version)
        VALUES (?, ?, 105.0, 100.0, ?, 'EXACT_DATE', 'dev', current_timestamp,
                'STANDARD_120', 'COMPLETE', 'COMPLETE', 120, 120,
                'feature-completeness-v1')
        """,
        [symbol, date_str, date_str],
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

    def test_symbol_missing(self):
        from vnalpha.data_availability.checks import get_symbol_master_status

        conn = _fresh_conn()
        assert get_symbol_master_status(conn, "NOTEXIST") is False


class TestGetCanonicalOhlcvStatus:
    def test_no_bars_returns_zero(self):
        from vnalpha.data_availability.checks import get_canonical_ohlcv_status

        conn = _fresh_conn()
        assert get_canonical_ohlcv_status(conn, "FPT", "2025-01-10", "2024-07-01") == 0

    def test_counts_bars_in_window(self):
        from vnalpha.data_availability.checks import get_canonical_ohlcv_status

        conn = _fresh_conn()
        for d in ["2025-01-02", "2025-01-03", "2025-01-06"]:
            _insert_canonical_bar(conn, "FPT", d)
        count = get_canonical_ohlcv_status(conn, "FPT", "2025-01-06", "2025-01-01")
        assert count == 3

    def test_excludes_bars_outside_window(self):
        from vnalpha.data_availability.checks import get_canonical_ohlcv_status

        conn = _fresh_conn()
        _insert_canonical_bar(conn, "FPT", "2024-12-31")
        _insert_canonical_bar(conn, "FPT", "2025-01-02")
        count = get_canonical_ohlcv_status(conn, "FPT", "2025-01-06", "2025-01-01")
        assert count == 1


class TestGetLatestCanonicalBarDate:
    def test_no_bars_returns_none(self):
        from vnalpha.data_availability.checks import get_latest_canonical_bar_date

        conn = _fresh_conn()
        assert get_latest_canonical_bar_date(conn, "FPT", "2025-01-10") is None

    def test_returns_latest_bar_at_or_before_target(self):
        from vnalpha.data_availability.checks import get_latest_canonical_bar_date

        conn = _fresh_conn()
        for d in ["2025-01-02", "2025-01-03", "2025-01-06"]:
            _insert_canonical_bar(conn, "FPT", d)
        assert get_latest_canonical_bar_date(conn, "FPT", "2025-01-10") == "2025-01-06"

    def test_ignores_bars_after_target(self):
        from vnalpha.data_availability.checks import get_latest_canonical_bar_date

        conn = _fresh_conn()
        _insert_canonical_bar(conn, "FPT", "2025-01-06")
        _insert_canonical_bar(conn, "FPT", "2025-01-20")
        assert get_latest_canonical_bar_date(conn, "FPT", "2025-01-10") == "2025-01-06"


class TestGetFeatureSnapshotStatus:
    def test_missing_returns_false(self):
        from vnalpha.data_availability.checks import get_feature_snapshot_status

        conn = _fresh_conn()
        assert get_feature_snapshot_status(conn, "FPT", "2025-01-06") is False

    def test_present_returns_true(self):
        from vnalpha.data_availability.checks import get_feature_snapshot_status

        conn = _fresh_conn()
        _insert_feature_snapshot(conn, "FPT", "2025-01-06")
        assert get_feature_snapshot_status(conn, "FPT", "2025-01-06") is True


class TestGetCandidateScoreStatus:
    def test_missing_returns_none(self):
        from vnalpha.data_availability.checks import get_candidate_score_status

        conn = _fresh_conn()
        assert get_candidate_score_status(conn, "FPT", "2025-01-06") is None

    def test_fresh_returns_class(self):
        from vnalpha.data_availability.checks import get_candidate_score_status

        conn = _fresh_conn()
        _insert_candidate_score(conn, "FPT", "2025-01-06", as_of_bar_date="2025-01-06")
        result = get_candidate_score_status(
            conn, "FPT", "2025-01-06", stale_after_calendar_days=7
        )
        assert result == "STRONG_CANDIDATE"

    def test_stale_returns_none(self):
        from vnalpha.data_availability.checks import get_candidate_score_status

        conn = _fresh_conn()
        _insert_candidate_score(conn, "FPT", "2025-01-06", as_of_bar_date="2024-11-01")
        result = get_candidate_score_status(
            conn, "FPT", "2025-01-06", stale_after_calendar_days=7
        )
        assert result is None


class TestComputeLookbackStart:
    def test_subtracts_days(self):
        from vnalpha.data_availability.checks import compute_lookback_start

        result = compute_lookback_start("2025-06-30", 420)
        assert result == "2024-05-06"

    def test_rejects_invalid_date(self):
        from vnalpha.data_availability.checks import compute_lookback_start
        from vnalpha.data_availability.dates import InvalidEnsureDateError

        with pytest.raises(InvalidEnsureDateError, match="Invalid target date"):
            compute_lookback_start("not-a-date", 30)


class TestWeekendNonTradingDate:
    """Task 3.8 — weekend and non-trading target dates work correctly."""

    def test_canonical_bars_counted_up_to_weekend_target(self):
        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")
        _insert_canonical_bar(conn, "FPT", "2025-01-03")  # Friday
        _insert_canonical_bar(conn, "FPT", "2025-01-02")  # Thursday

        from vnalpha.data_availability.checks import get_canonical_ohlcv_status

        # Target is Saturday — bars on/before Saturday should be counted
        count = get_canonical_ohlcv_status(conn, "FPT", "2025-01-04", "2025-01-01")
        assert count == 2

    def test_lookback_start_from_weekend(self):
        from vnalpha.data_availability.checks import compute_lookback_start

        # Sunday target
        result = compute_lookback_start("2025-01-05", 7)
        assert result == "2024-12-29"

    def test_ensure_with_weekend_target_uses_friday_data(self):
        from vnalpha.data_availability import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")
        _insert_symbol(conn, "VNINDEX")
        # Add enough bars (weekdays only, simulating market closure on weekends)
        for day in range(1, 125):
            from datetime import date, timedelta

            d = date(2024, 6, 1) + timedelta(days=day)
            if d.weekday() < 5:  # weekday only
                _insert_canonical_bar(conn, "FPT", d.isoformat())
                _insert_canonical_bar(conn, "VNINDEX", d.isoformat())
        _insert_feature_snapshot(conn, "FPT", "2025-01-04")
        _insert_candidate_score(conn, "FPT", "2025-01-04")

        policy = DataAvailabilityPolicy(auto_sync=False, min_required_bars=50)
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-01-04",
            policy=policy,  # Saturday
        )
        assert result.status.value == "READY"
