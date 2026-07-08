"""Tests for data_availability.checks — read-only warehouse queries."""

from __future__ import annotations

import duckdb

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
        (symbol, date, close, ma20, feature_data_status, feature_build_version, feature_generated_at)
        VALUES (?, ?, 105.0, 100.0, 'EXACT_DATE', 'dev', current_timestamp)
        """,
        [symbol, date_str],
    )


def _insert_candidate_score(conn, symbol, date_str, as_of_bar_date=None):
    import json

    lineage = {"as_of_bar_date": as_of_bar_date or date_str}
    conn.execute(
        """
        INSERT INTO candidate_score
        (symbol, date, score, candidate_class, setup_type,
         trend_score, relative_strength_score, volume_score,
         base_score, breakout_score, risk_quality_score,
         evidence_json, risk_flags_json, lineage_json)
        VALUES (?, ?, 0.75, 'STRONG_CANDIDATE', 'MOMENTUM_CONTINUATION',
                0.8, 0.7, 0.6, 0.5, 0.4, 0.9, '{}', '[]', ?)
        """,
        [symbol, date_str, json.dumps(lineage)],
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

    def test_handles_invalid_date(self):
        from vnalpha.data_availability.checks import compute_lookback_start

        result = compute_lookback_start("not-a-date", 30)
        assert result is not None
        assert len(result) == 10
