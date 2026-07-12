"""Tests for data_availability lock and observability event emission."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

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


def _noop_sync_symbols(conn, **kwargs):
    return {"total": 0, "inserted": 0}


def _noop_sync_ohlcv(conn, **kwargs):
    return {"inserted": 0, "skipped": 0}


def _noop_build_canonical(conn, **kwargs):
    return {"upserted": 0, "rejected": 0}


def _noop_build_features(conn, **kwargs):
    return {"built": 0, "skipped": 0}


def _noop_score_universe(conn, **kwargs):
    return 0


class TestEnsureLock:
    """Task 11.1-11.5 — file-based lock per symbol/date."""

    def test_acquire_creates_lock_file(self, tmp_path: Path):
        from vnalpha.data_availability.lock import EnsureLock

        lock = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path)
        assert lock.acquire() is True
        assert lock.lock_path.exists()
        lock.release()

    def test_release_removes_lock_file(self, tmp_path: Path):
        from vnalpha.data_availability.lock import EnsureLock

        lock = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path)
        lock.acquire()
        lock.release()
        assert not lock.lock_path.exists()

    def test_fresh_lock_blocks_second_acquire(self, tmp_path: Path):
        from vnalpha.data_availability.lock import EnsureLock

        lock1 = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path)
        lock2 = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path)
        assert lock1.acquire() is True
        assert lock2.acquire() is False
        lock1.release()

    def test_stale_lock_is_replaced(self, tmp_path: Path):
        from vnalpha.data_availability.lock import EnsureLock

        lock1 = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path, stale_seconds=1)
        lock1.acquire()
        # Artificially age the lock file
        lock_file = lock1.lock_path
        old_time = time.time() - 10
        import os

        os.utime(lock_file, (old_time, old_time))

        lock2 = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path, stale_seconds=1)
        assert lock2.acquire() is True
        lock2.release()

    def test_context_manager_releases_on_exit(self, tmp_path: Path):
        from vnalpha.data_availability.lock import EnsureLock

        with EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path) as lock:
            assert lock.lock_path.exists()
        assert not lock.lock_path.exists()

    def test_ensure_skips_when_lock_held(self, tmp_path: Path):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.lock import EnsureLock
        from vnalpha.data_availability.models import EnsureDataStatus
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")

        lock = EnsureLock("FPT", "2025-06-30", lock_dir=tmp_path)
        lock.acquire()

        policy = DataAvailabilityPolicy(auto_sync=True)
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            _lock_dir=tmp_path,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert result.status == EnsureDataStatus.PARTIAL
        assert "Another ensure flow" in result.warnings[0]
        lock.release()

    def test_ensure_releases_lock_on_completion(self, tmp_path: Path):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")

        policy = DataAvailabilityPolicy(auto_sync=False)
        ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            _lock_dir=tmp_path,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        lock_file = tmp_path / "data-ensure-FPT-2025-06-30.lock"
        assert not lock_file.exists()


class TestObservabilityEvents:
    """Task 10.10 — prove observability events are emitted during ensure."""

    def test_started_event_emitted(self, tmp_path: Path):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        events: list[str] = []

        def _capture_event(event_type, *args, **kwargs):
            events.append(event_type)

        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")
        policy = DataAvailabilityPolicy(auto_sync=False)

        with patch(
            "vnalpha.data_availability.observability.log_audit",
            side_effect=_capture_event,
        ):
            ensure_symbol_analysis_ready(
                conn,
                "FPT",
                "2025-06-30",
                policy=policy,
                _lock_dir=tmp_path,
                _sync_symbols_fn=_noop_sync_symbols,
                _sync_ohlcv_fn=_noop_sync_ohlcv,
                _build_canonical_fn=_noop_build_canonical,
                _build_features_fn=_noop_build_features,
                _score_universe_fn=_noop_score_universe,
            )

        assert "DATA_ENSURE_STARTED" in events

    def test_cache_hit_event_emitted(self, tmp_path: Path):
        import json

        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        events: list[str] = []

        def _capture_event(event_type, *args, **kwargs):
            events.append(event_type)

        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")
        _insert_symbol(conn, "VNINDEX")
        for symbol in ("FPT", "VNINDEX"):
            conn.execute(
                """
                INSERT INTO canonical_ohlcv
                (symbol, time, interval, open, high, low, close, volume,
                 selected_provider, quality_status, ingestion_run_id)
                VALUES (?, '2025-06-30', '1D', 10, 11, 9, 10.5, 1000,
                        'test', 'pass', 'test-run')
                """,
                [symbol],
            )
        conn.execute(
            """
            INSERT INTO feature_snapshot
            (symbol, date, close, feature_data_status, feature_build_version,
             feature_generated_at)
            VALUES ('FPT', '2025-06-30', 10.5, 'EXACT_DATE', 'test-v1',
                    current_timestamp)
            """
        )
        lineage = {
            "as_of_bar_date": "2025-06-30",
            "scoring_version": "test-v1",
            "feature_build_version": "test-v1",
            "selected_provider": "test",
            "ingestion_run_id": "test-run",
            "source_quality_status": "pass",
            "lineage_status": "COMPLETE",
        }
        conn.execute(
            """
            INSERT INTO candidate_score
            (symbol, date, score, candidate_class, setup_type,
             trend_score, relative_strength_score, volume_score,
             base_score, breakout_score, risk_quality_score,
             evidence_json, risk_flags_json, lineage_json)
            VALUES ('FPT', '2025-06-30', 0.75, 'STRONG_CANDIDATE', 'MOMENTUM_CONTINUATION',
                    0.8, 0.7, 0.6, 0.5, 0.4, 0.9, '{}', '[]', ?)
            """,
            [json.dumps(lineage)],
        )

        policy = DataAvailabilityPolicy(auto_sync=False, min_required_bars=1)
        with patch(
            "vnalpha.data_availability.observability.log_audit",
            side_effect=_capture_event,
        ):
            ensure_symbol_analysis_ready(
                conn,
                "FPT",
                "2025-06-30",
                policy=policy,
                _lock_dir=tmp_path,
                _sync_symbols_fn=_noop_sync_symbols,
                _sync_ohlcv_fn=_noop_sync_ohlcv,
                _sync_index_fn=_noop_sync_ohlcv,
                _build_canonical_fn=_noop_build_canonical,
                _build_features_fn=_noop_build_features,
                _score_universe_fn=_noop_score_universe,
            )

        assert "DATA_ENSURE_CACHE_HIT" in events

    def test_sync_events_emitted_on_auto_sync(self, tmp_path: Path):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        events: list[str] = []

        def _capture_event(event_type, *args, **kwargs):
            events.append(event_type)

        def _sync_symbols_that_inserts(conn, **kwargs):
            _insert_symbol(conn, "HPG")
            return {"total": 1, "inserted": 1}

        conn = _fresh_conn()
        policy = DataAvailabilityPolicy(auto_sync=True, min_required_bars=1)

        with patch(
            "vnalpha.data_availability.observability.log_audit",
            side_effect=_capture_event,
        ):
            ensure_symbol_analysis_ready(
                conn,
                "HPG",
                "2025-06-30",
                policy=policy,
                _lock_dir=tmp_path,
                _sync_symbols_fn=_sync_symbols_that_inserts,
                _sync_ohlcv_fn=_noop_sync_ohlcv,
                _sync_index_fn=_noop_sync_ohlcv,
                _build_canonical_fn=_noop_build_canonical,
                _build_features_fn=_noop_build_features,
                _score_universe_fn=_noop_score_universe,
            )

        assert "DATA_ENSURE_SYMBOLS_SYNC_STARTED" in events
        assert "DATA_ENSURE_SYMBOLS_SYNC_SUCCEEDED" in events

    def test_failed_event_on_unknown_symbol(self, tmp_path: Path):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        events: list[str] = []

        def _capture_event(event_type, *args, **kwargs):
            events.append(event_type)

        conn = _fresh_conn()
        policy = DataAvailabilityPolicy(auto_sync=False)

        with patch(
            "vnalpha.data_availability.observability.log_audit",
            side_effect=_capture_event,
        ):
            ensure_symbol_analysis_ready(
                conn,
                "UNKNOWN",
                "2025-06-30",
                policy=policy,
                _lock_dir=tmp_path,
                _sync_symbols_fn=_noop_sync_symbols,
                _sync_ohlcv_fn=_noop_sync_ohlcv,
                _build_canonical_fn=_noop_build_canonical,
                _build_features_fn=_noop_build_features,
                _score_universe_fn=_noop_score_universe,
            )

        assert "DATA_ENSURE_FAILED" in events
