"""Tests for QualityConfig in vnstock.core.settings."""

import os

import pytest

from vnstock.core.settings import QualityConfig, VnstockConfig, reset_config


class TestQualityConfigDefaults:
    def test_default_values(self):
        cfg = QualityConfig()
        assert cfg.enabled is False
        assert cfg.mode == "warn"
        assert cfg.attach_report is True
        assert cfg.max_error_examples == 20
        assert cfg.stale_price_board_seconds == 30
        assert cfg.stale_intraday_seconds == 60
        assert cfg.stale_daily_ohlcv_hours == 36
        assert cfg.check_missing_sessions is True
        assert cfg.check_ohlc_consistency is True
        assert cfg.check_price_scale is True
        assert cfg.check_session_time is False

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="mode must be"):
            QualityConfig(mode="invalid")

    def test_valid_modes(self):
        for m in ("off", "warn", "strict"):
            cfg = QualityConfig(mode=m)
            assert cfg.mode == m


class TestQualityConfigEnvVars:
    """Test that env vars are picked up in VnstockConfig._load_from_env."""

    def _make_config(self, **env_overrides):
        """Create a VnstockConfig with isolated env variables."""
        original = {}
        for k, v in env_overrides.items():
            original[k] = os.environ.get(k)
            os.environ[k] = v
        try:
            reset_config()
            return VnstockConfig()
        finally:
            for k, orig_v in original.items():
                if orig_v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = orig_v
            reset_config()

    def test_enabled_true_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_ENABLED="true")
        assert cfg.quality.enabled is True

    def test_enabled_false_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_ENABLED="false")
        assert cfg.quality.enabled is False

    def test_mode_strict_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_MODE="strict")
        assert cfg.quality.mode == "strict"

    def test_mode_off_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_MODE="off")
        assert cfg.quality.mode == "off"

    def test_invalid_mode_env_is_ignored(self):
        cfg = self._make_config(VNSTOCK_QUALITY_MODE="garbage")
        assert cfg.quality.mode == "warn"  # default unchanged

    def test_attach_report_false_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_ATTACH_REPORT="false")
        assert cfg.quality.attach_report is False

    def test_stale_price_board_seconds_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_STALE_PRICE_BOARD_SECONDS="15")
        assert cfg.quality.stale_price_board_seconds == 15

    def test_stale_intraday_seconds_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_STALE_INTRADAY_SECONDS="120")
        assert cfg.quality.stale_intraday_seconds == 120

    def test_stale_daily_ohlcv_hours_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_STALE_DAILY_OHLCV_HOURS="48")
        assert cfg.quality.stale_daily_ohlcv_hours == 48

    def test_check_missing_sessions_false_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_CHECK_MISSING_SESSIONS="false")
        assert cfg.quality.check_missing_sessions is False

    def test_check_session_time_true_from_env(self):
        cfg = self._make_config(VNSTOCK_QUALITY_CHECK_SESSION_TIME="true")
        assert cfg.quality.check_session_time is True

    def test_invalid_int_env_is_ignored(self):
        cfg = self._make_config(
            VNSTOCK_QUALITY_STALE_PRICE_BOARD_SECONDS="not_a_number"
        )
        assert cfg.quality.stale_price_board_seconds == 30  # default unchanged
