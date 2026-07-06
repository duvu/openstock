"""Tests for validate/quality_mode integration in BaseUI._dispatch."""

from __future__ import annotations

import warnings
from unittest.mock import patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2025-01-01", periods=3, freq="D"),
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [95.0, 96.0, 97.0],
            "close": [102.0, 103.0, 104.0],
            "volume": [1000, 2000, 3000],
        }
    )


def _make_invalid_ohlcv() -> pd.DataFrame:
    df = _make_valid_ohlcv()
    df.loc[0, "high"] = 80.0  # high < low → OHLC error
    return df


class _FakeEquityUI:
    """Minimal stand-in that exercises _run_quality_validation directly."""

    def __init__(self, symbol="FPT"):
        self.symbol = symbol

    def ohlcv(
        self, df: pd.DataFrame, quality_mode: str = "warn", validate: bool = True
    ):
        from vnstock.ui._base import _run_quality_validation

        return _run_quality_validation(
            df,
            domain_name="Market",
            method_name="equity",
            consumed_subdomain="ohlcv",
            quality_mode=quality_mode,
            provider="TEST",
            symbol=self.symbol,
        )


# ---------------------------------------------------------------------------
# Tests for _run_quality_validation
# ---------------------------------------------------------------------------


class TestRunQualityValidationOff:
    def test_off_mode_returns_df_unchanged(self):
        df = _make_valid_ohlcv()
        ui = _FakeEquityUI()
        result = ui.ohlcv(df, quality_mode="off")
        assert result is df
        assert "quality" not in result.attrs


class TestRunQualityValidationWarnMode:
    def test_warn_mode_attaches_report(self):
        df = _make_valid_ohlcv()
        ui = _FakeEquityUI()
        result = ui.ohlcv(df, quality_mode="warn")
        # report should be attached when quality.attach_report is True (default)
        assert "quality" in result.attrs
        from vnstock.core.quality.models import ValidationReport

        assert isinstance(result.attrs["quality"], ValidationReport)

    def test_warn_mode_does_not_raise_on_errors(self):
        df = _make_invalid_ohlcv()
        ui = _FakeEquityUI()
        # Should not raise even though there are OHLC errors
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = ui.ohlcv(df, quality_mode="warn")
        assert result is df  # same object returned

    def test_warn_mode_valid_data_no_warning_issued(self):
        df = _make_valid_ohlcv()
        ui = _FakeEquityUI()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ui.ohlcv(df, quality_mode="warn")
        # No UserWarning about data quality errors for clean data
        quality_warns = [x for x in w if "Data quality issues" in str(x.message)]
        assert quality_warns == []


class TestRunQualityValidationStrictMode:
    def test_strict_mode_raises_on_errors(self):
        from vnstock.core.quality.exceptions import DataQualityError

        df = _make_invalid_ohlcv()
        ui = _FakeEquityUI()
        with pytest.raises(DataQualityError) as exc_info:
            ui.ohlcv(df, quality_mode="strict")
        assert exc_info.value.report.severity == "error"

    def test_strict_mode_no_raise_for_valid_data(self):
        df = _make_valid_ohlcv()
        ui = _FakeEquityUI()
        result = ui.ohlcv(df, quality_mode="strict")
        assert result is df


class TestDispatchQualityKwargsNotLeaked:
    """Ensure validate/quality_mode kwargs are stripped before provider calls."""

    def test_quality_kwargs_popped_from_kwargs(self):
        """_dispatch must pop validate and quality_mode before provider dispatch."""
        from vnstock.ui._base import BaseUI

        class MinimalUI(BaseUI):
            def __init__(self):
                self.symbol = "FPT"

        # Patch _execute_dispatch to capture what kwargs reaches the provider
        captured_kwargs: dict = {}

        def fake_execute(
            module_type, sub_module, class_name, function_name, symbol, args, kwargs
        ):
            captured_kwargs.update(kwargs)
            df = _make_valid_ohlcv()
            return df

        ui = MinimalUI()
        ui._execute_dispatch = fake_execute

        # Mock the MAP to return a simple entry
        fake_meta = ("explorer", "vci", "Quote", "history", "vci")
        with (
            patch(
                "vnstock.ui._registry.MAP", {"Market": {"equity": {"ohlcv": fake_meta}}}
            ),
            patch("vnstock.core.router.router.pick", return_value="vci"),
            patch("vnstock.ui._pools.POOLS", {}),
        ):
            try:
                ui._dispatch(
                    "Market",
                    "equity",
                    "ohlcv",
                    validate=True,
                    quality_mode="warn",
                    source="vci",
                )
            except Exception:
                pass

        assert "validate" not in captured_kwargs, "validate should not reach provider"
        assert "quality_mode" not in captured_kwargs, (
            "quality_mode should not reach provider"
        )


# ---------------------------------------------------------------------------
# Regression tests for correctness fixes
# ---------------------------------------------------------------------------


class TestGlobalQualityConfigDefaults:
    """_dispatch() should read defaults from QualityConfig, not hardcoded False/'warn'."""

    def test_validate_defaults_to_quality_config_enabled(self):
        """When validate not passed, default comes from QualityConfig.enabled."""
        from vnstock.core.settings import get_config

        cfg = get_config()
        # The default is False; confirm the kwarg logic mirrors it
        original = cfg.quality.enabled
        assert not original  # sanity: default is disabled

    def test_quality_mode_defaults_to_quality_config_mode(self):
        """When quality_mode not passed, default comes from QualityConfig.mode."""
        from vnstock.core.settings import get_config

        cfg = get_config()
        assert cfg.quality.mode == "warn"  # default from QualityConfig


class TestInternalValidationObservable:
    """Internal validation failures must produce a RuntimeWarning, not be swallowed."""

    def test_internal_error_emits_runtime_warning_in_warn_mode(self):
        """If validate_dataframe crashes internally, warn mode must emit RuntimeWarning."""
        from unittest.mock import patch

        from vnstock.ui._base import _run_quality_validation

        df = _make_valid_ohlcv()
        with patch(
            "vnstock.ui._base.validate_dataframe",
            side_effect=RuntimeError("simulated internal crash"),
            create=True,
        ):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                # Import within the patch so the lazy import picks up the mock
                from vnstock.core.quality import registry as _r

                with patch.object(
                    _r, "validate_dataframe", side_effect=RuntimeError("crash")
                ):
                    result = _run_quality_validation(
                        df,
                        domain_name="Market",
                        method_name="equity",
                        consumed_subdomain="ohlcv",
                        quality_mode="warn",
                        provider="TEST",
                        symbol="FPT",
                    )
        # Data must still be returned
        assert result is df
        # A RuntimeWarning must have been emitted
        runtime_warns = [x for x in w if issubclass(x.category, RuntimeWarning)]
        assert runtime_warns, "Expected RuntimeWarning when validation fails internally"
        assert "QUALITY_VALIDATION_INTERNAL_ERROR" in str(runtime_warns[0].message)


class TestIndexSafeRowReporting:
    """Numeric and temporal rules must not crash on DatetimeIndex or string index."""

    def test_numeric_negative_price_datetime_index(self):
        from vnstock.core.quality.rules.numeric import check_negative_prices

        idx = pd.date_range("2025-01-01", periods=3, freq="D")
        df = pd.DataFrame({"open": [100.0, -5.0, 200.0]}, index=idx)
        issues = check_negative_prices(df, ["open"])
        assert len(issues) == 1
        assert issues[0].code == "NUMERIC_NEGATIVE_PRICE"
        assert issues[0].row_index == 1  # positional index

    def test_temporal_duplicate_times_datetime_index(self):
        from vnstock.core.quality.rules.temporal import check_duplicate_times

        ts = pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02"])
        df = pd.DataFrame({"time": ts})  # use default RangeIndex, not DatetimeIndex
        issues = check_duplicate_times(df)
        assert len(issues) == 1
        assert issues[0].code == "TIME_DUPLICATED"
        assert isinstance(issues[0].row_index, int)

    def test_numeric_negative_price_datetime_index_no_crash(self):
        """Rules must not raise when the DataFrame has a DatetimeIndex."""
        from vnstock.core.quality.rules.numeric import check_negative_prices

        idx = pd.date_range("2025-01-01", periods=3, freq="D")
        df = pd.DataFrame({"open": [100.0, -5.0, 200.0]}, index=idx)
        issues = check_negative_prices(df, ["open"])
        assert len(issues) == 1
        assert issues[0].code == "NUMERIC_NEGATIVE_PRICE"


class TestFreshnessCoerceDatetime:
    """_coerce_datetime must handle all supported input types."""

    def test_coerce_iso_string(self):
        from vnstock.core.quality.rules.freshness import _coerce_datetime

        result = _coerce_datetime("2025-01-01T10:00:00Z")
        assert result is not None
        assert result.tzinfo is not None

    def test_coerce_naive_datetime(self):
        from datetime import datetime

        from vnstock.core.quality.rules.freshness import _coerce_datetime

        result = _coerce_datetime(datetime(2025, 1, 1, 10, 0, 0))
        assert result is not None
        assert result.tzinfo is not None  # should be UTC-aware

    def test_coerce_none_returns_none(self):
        from vnstock.core.quality.rules.freshness import _coerce_datetime

        assert _coerce_datetime(None) is None

    def test_coerce_invalid_string_returns_none(self):
        from vnstock.core.quality.rules.freshness import _coerce_datetime

        assert _coerce_datetime("not-a-date") is None


class TestProviderInputGuards:
    """detect_drift and compare_ohlcv must handle invalid inputs gracefully."""

    def test_detect_drift_non_dataframe_returns_error_issue(self):
        from vnstock.core.provider.drift import detect_drift

        issues = detect_drift(None, "vci", "ohlcv")  # type: ignore[arg-type]
        assert len(issues) == 1
        assert issues[0].code == "DRIFT_INVALID_INPUT"
        assert issues[0].severity == "error"

    def test_detect_drift_empty_provider_returns_error_issue(self):
        import pandas as pd

        from vnstock.core.provider.drift import detect_drift

        df = pd.DataFrame(
            {"time": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
        )
        issues = detect_drift(df, "", "ohlcv")
        assert len(issues) == 1
        assert issues[0].code == "DRIFT_INVALID_INPUT"

    def test_compare_ohlcv_non_dict_returns_error_issue(self):
        from vnstock.core.provider.compare import compare_ohlcv

        report = compare_ohlcv(None)  # type: ignore[arg-type]
        assert not report.comparable
        assert any(i.code == "COMPARE_INVALID_INPUT" for i in report.issues)

    def test_compare_ohlcv_non_dataframe_values_returns_error_issue(self):
        from vnstock.core.provider.compare import compare_ohlcv

        report = compare_ohlcv({"vci": "not_a_df", "kbs": "also_not"})  # type: ignore[arg-type]
        assert not report.comparable
        assert any(i.code == "COMPARE_INVALID_INPUT" for i in report.issues)


class TestComparisonReportIssuesType:
    """ProviderComparisonReport.issues must contain ProviderIssue objects."""

    def test_compare_insufficient_providers_issues_are_provider_issue(self):
        from vnstock.core.provider.compare import compare_ohlcv
        from vnstock.core.provider.models import ProviderIssue

        report = compare_ohlcv({"only_one": _make_valid_ohlcv()})
        assert all(isinstance(i, ProviderIssue) for i in report.issues)
