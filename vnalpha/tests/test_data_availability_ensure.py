"""Tests for data_availability.ensure — full pipeline with dependency injection."""

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


# DI no-op stubs
def _noop_sync_symbols(conn, **kwargs):
    return {"total": 0, "inserted": 0}


def _noop_sync_ohlcv(conn, universe, start, end, **kwargs):
    return {"inserted": 0, "skipped": 0}


def _noop_build_canonical(conn, symbol, **kwargs):
    return {"upserted": 0, "rejected": 0}


def _noop_build_features(conn, target_date, universe, benchmark_symbol, **kwargs):
    return {"built": 0, "skipped": 0}


def _noop_score_universe(conn, date, universe, **kwargs):
    return 0


class TestCacheHit:
    """If candidate_score is fresh, return READY immediately without syncing."""

    def test_returns_ready_on_cache_hit(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.models import EnsureDataStatus
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        conn = _fresh_conn()
        date = "2025-06-30"
        _insert_symbol(conn, "FPT")
        _insert_candidate_score(conn, "FPT", date, as_of_bar_date=date)

        policy = DataAvailabilityPolicy(auto_sync=True)
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            date,
            policy=policy,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert result.status == EnsureDataStatus.READY


class TestNoAutoSync:
    """When auto_sync=False, missing data yields PARTIAL/FAILED without calling sync."""

    def test_missing_symbol_returns_failed_without_sync(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.models import EnsureDataStatus
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        sync_called = []

        def _track_sync(conn, **kwargs):
            sync_called.append(1)
            return {"total": 0, "inserted": 0}

        conn = _fresh_conn()
        policy = DataAvailabilityPolicy(auto_sync=False)
        result = ensure_symbol_analysis_ready(
            conn,
            "UNKNOWN",
            "2025-06-30",
            policy=policy,
            _sync_symbols_fn=_track_sync,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert result.status in (EnsureDataStatus.PARTIAL, EnsureDataStatus.FAILED)
        assert len(sync_called) == 0


class TestAutoSyncPath:
    """With auto_sync=True and injected fns, ensure calls sync + build as needed."""

    def test_missing_symbol_triggers_sync_symbols(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        sync_called = []

        def _track_sync_symbols(conn, **kwargs):
            sync_called.append("symbols")
            _insert_symbol(conn, "FPT")
            return {"total": 1, "inserted": 1}

        conn = _fresh_conn()
        policy = DataAvailabilityPolicy(auto_sync=True, min_required_bars=1)
        ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            _sync_symbols_fn=_track_sync_symbols,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert "symbols" in sync_called

    def test_missing_ohlcv_triggers_sync_and_build(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        actions = []

        def _track_ohlcv(conn, universe, start, end, **kwargs):
            actions.append("sync_ohlcv")
            return {"inserted": 5, "skipped": 0}

        def _track_canonical(conn, symbol, **kwargs):
            actions.append("build_canonical")
            return {"upserted": 5, "rejected": 0}

        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")
        policy = DataAvailabilityPolicy(auto_sync=True, min_required_bars=1)
        ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_track_ohlcv,
            _build_canonical_fn=_track_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert "sync_ohlcv" in actions
        assert "build_canonical" in actions


class TestFullHappyPath:
    """All data present → READY, no sync calls."""

    def _make_dates(self, n=130):
        from datetime import date, timedelta

        base = date(2025, 6, 30)
        return [(base - timedelta(days=i)).isoformat() for i in range(n)]

    def test_all_data_present_returns_ready(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.models import EnsureDataStatus
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        conn = _fresh_conn()
        date = "2025-06-30"
        _insert_symbol(conn, "FPT")
        _insert_symbol(conn, "VNINDEX")
        _insert_canonical_bars(conn, "FPT", self._make_dates(130))
        _insert_canonical_bars(conn, "VNINDEX", self._make_dates(130))
        _insert_feature_snapshot(conn, "FPT", date)
        _insert_candidate_score(conn, "FPT", date, as_of_bar_date=date)

        policy = DataAvailabilityPolicy(auto_sync=False, min_required_bars=120)
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            date,
            policy=policy,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert result.status == EnsureDataStatus.READY


class TestNoCrashOnSyncFailure:
    """Sync/build exceptions must NOT propagate; result should be PARTIAL or FAILED."""

    def test_sync_exception_yields_partial(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.models import EnsureDataStatus
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        def _exploding_sync(conn, **kwargs):
            raise RuntimeError("service unavailable")

        conn = _fresh_conn()
        policy = DataAvailabilityPolicy(auto_sync=True)
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            _sync_symbols_fn=_exploding_sync,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert result.status in (EnsureDataStatus.PARTIAL, EnsureDataStatus.FAILED)


class TestResultStructure:
    def test_result_has_required_fields(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.models import EnsureDataResult
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        conn = _fresh_conn()
        policy = DataAvailabilityPolicy()
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert isinstance(result, EnsureDataResult)
        assert result.symbol == "FPT"
        assert result.target_date == "2025-06-30"
        assert isinstance(result.actions_taken, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.errors, list)

    def test_to_panel_dict(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        conn = _fresh_conn()
        policy = DataAvailabilityPolicy()
        result = ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        panel = result.to_panel_dict()
        assert "status" in panel
        assert "actions_taken" in panel


class TestClientDI:
    """Task 5.2 — VnstockClient DI is threaded to sync functions."""

    def test_client_passed_to_sync_symbols(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        received_kwargs: list[dict] = []

        def _capture_sync(conn, **kwargs):
            received_kwargs.append(kwargs)
            _insert_symbol(conn, "FPT")
            return {"total": 1, "inserted": 1}

        conn = _fresh_conn()
        fake_client = object()
        policy = DataAvailabilityPolicy(auto_sync=True, min_required_bars=1)
        ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            client=fake_client,
            _sync_symbols_fn=_capture_sync,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert received_kwargs[0].get("client") is fake_client

    def test_client_passed_to_sync_ohlcv(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        received_kwargs: list[dict] = []

        def _capture_ohlcv(conn, **kwargs):
            received_kwargs.append(kwargs)
            return {"inserted": 0, "skipped": 0}

        conn = _fresh_conn()
        _insert_symbol(conn, "FPT")
        fake_client = object()
        policy = DataAvailabilityPolicy(auto_sync=True, min_required_bars=200)
        ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            client=fake_client,
            _sync_symbols_fn=_noop_sync_symbols,
            _sync_ohlcv_fn=_capture_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert any(kw.get("client") is fake_client for kw in received_kwargs)

    def test_source_and_base_url_passed_through(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        received_kwargs: list[dict] = []

        def _capture_sync(conn, **kwargs):
            received_kwargs.append(kwargs)
            _insert_symbol(conn, "FPT")
            return {"total": 1, "inserted": 1}

        conn = _fresh_conn()
        policy = DataAvailabilityPolicy(
            auto_sync=True,
            min_required_bars=1,
            source="VCI",
            base_url="http://test:9999",
        )
        ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2025-06-30",
            policy=policy,
            _sync_symbols_fn=_capture_sync,
            _sync_ohlcv_fn=_noop_sync_ohlcv,
            _build_canonical_fn=_noop_build_canonical,
            _build_features_fn=_noop_build_features,
            _score_universe_fn=_noop_score_universe,
        )
        assert received_kwargs[0]["source"] == "VCI"
        assert received_kwargs[0]["base_url"] == "http://test:9999"


class TestFakeProviderFixtures:
    """Task 5.4 — reusable fake provider response helpers for testing."""

    def test_fake_sync_populates_symbol_master(self):
        from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
        from vnalpha.data_availability.models import EnsureDataAction, EnsureDataStatus
        from vnalpha.data_availability.policy import DataAvailabilityPolicy

        def fake_sync_symbols(conn, **kwargs):
            _insert_symbol(conn, "HPG")
            return {"total": 1, "inserted": 1}

        def fake_sync_ohlcv(conn, **kwargs):
            from datetime import date, timedelta

            base = date(2025, 6, 30)
            for i in range(130):
                d = base - timedelta(days=i)
                if d.weekday() < 5:
                    _insert_canonical_bars(conn, "HPG", [d.isoformat()])
            return {"inserted": 130, "skipped": 0}

        def fake_build_canonical(conn, **kwargs):
            return {"upserted": 130, "rejected": 0}

        def fake_build_features(conn, **kwargs):
            _insert_feature_snapshot(conn, "HPG", "2025-06-30")
            return {"built": 1, "skipped": 0}

        def fake_score(conn, **kwargs):
            _insert_candidate_score(conn, "HPG", "2025-06-30")
            return 1

        conn = _fresh_conn()
        _insert_symbol(conn, "VNINDEX")
        _insert_canonical_bars(conn, "VNINDEX", self._make_dates(130))
        policy = DataAvailabilityPolicy(auto_sync=True, min_required_bars=50)
        result = ensure_symbol_analysis_ready(
            conn,
            "HPG",
            "2025-06-30",
            policy=policy,
            _sync_symbols_fn=fake_sync_symbols,
            _sync_ohlcv_fn=fake_sync_ohlcv,
            _build_canonical_fn=fake_build_canonical,
            _build_features_fn=fake_build_features,
            _score_universe_fn=fake_score,
        )
        assert result.status == EnsureDataStatus.READY
        assert EnsureDataAction.SYMBOLS_SYNCED in result.actions_taken
        assert EnsureDataAction.SCORED in result.actions_taken

    def _make_dates(self, n=130):
        from datetime import date, timedelta

        base = date(2025, 6, 30)
        return [(base - timedelta(days=i)).isoformat() for i in range(n)]
