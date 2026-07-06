"""Tests for vnstock.core.quality.validators.ohlcv."""

import pandas as pd

from vnstock.core.quality.validators.ohlcv import OHLCVValidator

_VALIDATOR = OHLCVValidator()


def _make_ohlcv(**overrides) -> pd.DataFrame:
    data = {
        "time": pd.date_range("2025-01-01", periods=5, freq="D"),
        "open": [100.0, 101.0, 102.0, 103.0, 104.0],
        "high": [105.0, 106.0, 107.0, 108.0, 109.0],
        "low": [95.0, 96.0, 97.0, 98.0, 99.0],
        "close": [102.0, 103.0, 104.0, 105.0, 106.0],
        "volume": [1000, 2000, 3000, 4000, 5000],
    }
    data.update(overrides)
    return pd.DataFrame(data)


class TestOHLCVValidatorValidData:
    def test_valid_dataframe_no_errors(self):
        df = _make_ohlcv()
        report = _VALIDATOR.validate(df, provider="TEST", symbol="FPT", interval="1D")
        assert report.valid is True
        assert report.errors == []

    def test_report_metadata(self):
        df = _make_ohlcv()
        report = _VALIDATOR.validate(df, provider="DNSE", symbol="VNM", interval="1D")
        assert report.provider == "DNSE"
        assert report.symbol == "VNM"
        assert report.interval == "1D"
        assert report.dataset_type == "ohlcv"
        assert report.row_count == 5


class TestOHLCVValidatorSchemaErrors:
    def test_missing_required_column(self):
        df = _make_ohlcv()
        df = df.drop(columns=["close"])
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "SCHEMA_MISSING_COLUMN" in codes
        assert report.valid is False

    def test_empty_dataframe(self):
        df = _make_ohlcv().iloc[0:0]
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "SCHEMA_EMPTY_DATAFRAME" in codes
        assert report.valid is False


class TestOHLCVValidatorOHLCConsistency:
    def test_high_below_low(self):
        df = _make_ohlcv()
        df.loc[2, "high"] = 90.0  # high < low at row 2
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "OHLC_HIGH_BELOW_LOW" in codes
        assert report.valid is False

    def test_high_below_open(self):
        df = _make_ohlcv()
        df.loc[0, "high"] = 99.0  # high < open (100)
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "OHLC_HIGH_BELOW_OPEN" in codes

    def test_high_below_close(self):
        df = _make_ohlcv()
        df.loc[0, "high"] = 101.0  # high < close (102)
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "OHLC_HIGH_BELOW_CLOSE" in codes

    def test_low_above_open(self):
        df = _make_ohlcv()
        df.loc[0, "low"] = 101.0  # low > open (100)
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "OHLC_LOW_ABOVE_OPEN" in codes

    def test_low_above_close(self):
        df = _make_ohlcv()
        df.loc[0, "low"] = 103.0  # low > close (102)
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "OHLC_LOW_ABOVE_CLOSE" in codes


class TestOHLCVValidatorNumericIssues:
    def test_negative_price(self):
        df = _make_ohlcv()
        df.loc[0, "close"] = -1.0
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "NUMERIC_NEGATIVE_PRICE" in codes

    def test_negative_volume(self):
        df = _make_ohlcv()
        df.loc[1, "volume"] = -100
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "NUMERIC_NEGATIVE_VOLUME" in codes


class TestOHLCVValidatorTemporalIssues:
    def test_duplicate_timestamps(self):
        df = _make_ohlcv()
        df.loc[2, "time"] = df.loc[1, "time"]  # duplicate
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.warnings]
        assert "TIME_DUPLICATED" in codes

    def test_non_monotonic_times(self):
        df = _make_ohlcv()
        # Swap rows 0 and 4 to break monotonic ordering
        df.loc[0, "time"] = pd.Timestamp("2025-01-10")
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.warnings]
        assert "TIME_NOT_MONOTONIC" in codes
