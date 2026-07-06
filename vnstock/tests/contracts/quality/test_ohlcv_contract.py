"""Provider contract tests for OHLCV validators.

These tests use static sample DataFrames that represent typical provider
output shapes from DNSE, KBS, and VCI. They do NOT call any external API.
"""

import pandas as pd

from vnstock.core.quality.registry import validate_dataframe


def _dnse_ohlcv_sample() -> pd.DataFrame:
    """DNSE-shaped OHLCV sample (daily bars for FPT)."""
    return pd.DataFrame(
        {
            "time": pd.date_range("2025-01-02", periods=5, freq="D"),
            "open": [74_600.0, 75_000.0, 75_500.0, 76_000.0, 75_800.0],
            "high": [75_200.0, 75_800.0, 76_200.0, 76_500.0, 76_300.0],
            "low": [74_000.0, 74_500.0, 75_000.0, 75_500.0, 75_200.0],
            "close": [74_900.0, 75_300.0, 75_800.0, 76_200.0, 76_000.0],
            "volume": [500_000, 620_000, 480_000, 710_000, 590_000],
        }
    )


def _kbs_ohlcv_sample() -> pd.DataFrame:
    """KBS-shaped OHLCV sample (daily bars for HPG)."""
    return pd.DataFrame(
        {
            "time": pd.date_range("2025-01-02", periods=5, freq="D"),
            "open": [27_500.0, 27_800.0, 27_200.0, 27_600.0, 27_900.0],
            "high": [28_000.0, 28_300.0, 27_700.0, 28_100.0, 28_400.0],
            "low": [27_200.0, 27_500.0, 26_900.0, 27_300.0, 27_600.0],
            "close": [27_700.0, 28_100.0, 27_400.0, 27_900.0, 28_200.0],
            "volume": [1_200_000, 980_000, 1_500_000, 1_100_000, 870_000],
        }
    )


def _vci_ohlcv_sample() -> pd.DataFrame:
    """VCI-shaped OHLCV sample (weekly bars for VNM)."""
    return pd.DataFrame(
        {
            "time": pd.date_range("2025-01-06", periods=4, freq="W-MON"),
            "open": [81_000.0, 82_500.0, 80_000.0, 83_000.0],
            "high": [83_000.0, 84_000.0, 82_000.0, 85_000.0],
            "low": [80_000.0, 81_500.0, 79_000.0, 82_000.0],
            "close": [82_500.0, 83_500.0, 81_000.0, 84_500.0],
            "volume": [2_000_000, 2_200_000, 1_800_000, 2_500_000],
        }
    )


class TestDNSEOHLCVContract:
    def test_valid_sample(self):
        df = _dnse_ohlcv_sample()
        report = validate_dataframe(
            df, dataset_type="ohlcv", provider="DNSE", symbol="FPT"
        )
        assert report.valid is True, (
            f"Unexpected errors: {[e.code for e in report.errors]}"
        )

    def test_has_all_required_columns(self):
        df = _dnse_ohlcv_sample()
        for col in ("time", "open", "high", "low", "close", "volume"):
            assert col in df.columns

    def test_no_ohlc_inconsistency(self):
        df = _dnse_ohlcv_sample()
        report = validate_dataframe(
            df, dataset_type="ohlcv", provider="DNSE", symbol="FPT"
        )
        ohlc_errors = [e for e in report.errors if e.code.startswith("OHLC_")]
        assert ohlc_errors == []


class TestKBSOHLCVContract:
    def test_valid_sample(self):
        df = _kbs_ohlcv_sample()
        report = validate_dataframe(
            df, dataset_type="ohlcv", provider="KBS", symbol="HPG"
        )
        assert report.valid is True, (
            f"Unexpected errors: {[e.code for e in report.errors]}"
        )

    def test_monotonic_timestamps(self):
        df = _kbs_ohlcv_sample()
        report = validate_dataframe(
            df, dataset_type="ohlcv", provider="KBS", symbol="HPG"
        )
        time_warns = [w for w in report.warnings if w.code == "TIME_NOT_MONOTONIC"]
        assert time_warns == []


class TestVCIOHLCVContract:
    def test_valid_sample(self):
        df = _vci_ohlcv_sample()
        report = validate_dataframe(
            df, dataset_type="ohlcv", provider="VCI", symbol="VNM"
        )
        assert report.valid is True, (
            f"Unexpected errors: {[e.code for e in report.errors]}"
        )


class TestOHLCVContractErrorDetection:
    """Ensure validators catch contract violations in provider-shaped data."""

    def test_missing_volume_column(self):
        df = _dnse_ohlcv_sample().drop(columns=["volume"])
        report = validate_dataframe(
            df, dataset_type="ohlcv", provider="DNSE", symbol="FPT"
        )
        assert not report.valid
        assert any(e.code == "SCHEMA_MISSING_COLUMN" for e in report.errors)

    def test_ohlc_inconsistency_in_sample(self):
        df = _dnse_ohlcv_sample()
        df.loc[0, "high"] = 73_000.0  # high < low
        report = validate_dataframe(
            df, dataset_type="ohlcv", provider="DNSE", symbol="FPT"
        )
        assert not report.valid
        assert any(e.code == "OHLC_HIGH_BELOW_LOW" for e in report.errors)
