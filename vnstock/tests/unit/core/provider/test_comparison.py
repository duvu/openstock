"""
Unit tests for vnstock/core/provider/comparison.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vnstock.core.provider.comparison import (
    compare_coverage,
    compare_freshness,
    compare_intraday_shape,
    compare_ohlcv,
    compare_quote,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ohlcv(n: int = 5, start: str = "2024-01-01") -> pd.DataFrame:
    times = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame(
        {
            "time": times,
            "open": np.linspace(100, 110, n),
            "high": np.linspace(105, 115, n),
            "low": np.linspace(95, 105, n),
            "close": np.linspace(102, 112, n),
            "volume": np.linspace(1000, 2000, n).astype(int),
        }
    )


def make_quote(symbols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": symbols,
            "close_price": [100.0 + i for i in range(len(symbols))],
        }
    )


# ---------------------------------------------------------------------------
# compare_ohlcv
# ---------------------------------------------------------------------------


class TestCompareOHLCV:
    def test_identical_dfs_have_zero_diff(self):
        df = make_ohlcv()
        result = compare_ohlcv(df, df.copy())
        assert result["aligned_rows"] == 5
        assert result["price_diffs"]["close"]["max_abs_diff"] == pytest.approx(0.0)
        assert result["volume_diff"]["max_abs_diff"] == pytest.approx(0.0)

    def test_detects_price_difference(self):
        df_a = make_ohlcv()
        df_b = make_ohlcv()
        df_b["close"] = df_b["close"] + 1.0
        result = compare_ohlcv(df_a, df_b)
        assert result["price_diffs"]["close"]["max_abs_diff"] == pytest.approx(1.0)

    def test_reports_non_overlapping_rows(self):
        df_a = make_ohlcv(5, "2024-01-01")
        df_b = make_ohlcv(5, "2024-01-06")
        result = compare_ohlcv(df_a, df_b)
        assert result["aligned_rows"] == 0
        assert result["only_in_a"] == 5
        assert result["only_in_b"] == 5

    def test_raises_on_missing_column(self):
        df_a = make_ohlcv()
        df_b = make_ohlcv().drop(columns=["close"])
        with pytest.raises(ValueError, match="missing required columns"):
            compare_ohlcv(df_a, df_b)

    def test_within_tolerance_flag(self):
        df_a = make_ohlcv()
        df_b = make_ohlcv()
        df_b["close"] = df_b["close"] + 0.01
        result = compare_ohlcv(df_a, df_b, price_tolerance=1.0)
        assert result["price_diffs"]["close"]["within_tolerance"] is True

    def test_max_close_diff_pct_is_present(self):
        df_a = make_ohlcv()
        df_b = make_ohlcv()
        result = compare_ohlcv(df_a, df_b)
        assert "max_close_diff_pct" in result


# ---------------------------------------------------------------------------
# compare_quote
# ---------------------------------------------------------------------------


class TestCompareQuote:
    def test_identical_quotes_zero_diff(self):
        df = make_quote(["FPT", "VCB"])
        result = compare_quote(df, df.copy())
        assert result["aligned_symbols"] == 2
        assert result["column_diffs"]["close_price"]["max_abs_diff"] == pytest.approx(
            0.0
        )

    def test_detects_symbol_mismatch(self):
        df_a = make_quote(["FPT", "VCB"])
        df_b = make_quote(["FPT", "TCB"])
        result = compare_quote(df_a, df_b)
        assert "VCB" in result["only_in_a"]
        assert "TCB" in result["only_in_b"]

    def test_raises_on_missing_symbol_col(self):
        df = make_quote(["FPT"])
        df2 = df.rename(columns={"symbol": "ticker"})
        with pytest.raises(ValueError):
            compare_quote(df, df2)


# ---------------------------------------------------------------------------
# compare_intraday_shape
# ---------------------------------------------------------------------------


class TestCompareIntradayShape:
    def test_same_schema_no_column_diff(self):
        df = pd.DataFrame(
            {
                "time": pd.date_range("2024-01-01", periods=3, freq="min"),
                "price": [100, 101, 102],
                "volume": [10, 20, 30],
            }
        )
        result = compare_intraday_shape(df, df.copy())
        assert result["column_diff"]["only_in_provider_a"] == []
        assert result["column_diff"]["only_in_provider_b"] == []

    def test_detects_column_differences(self):
        df_a = pd.DataFrame({"time": [1, 2], "price": [100, 101], "extra": [1, 2]})
        df_b = pd.DataFrame({"time": [1, 2], "price": [100, 101]})
        result = compare_intraday_shape(df_a, df_b)
        assert "extra" in result["column_diff"]["only_in_provider_a"]

    def test_time_monotonicity(self):
        times = pd.date_range("2024-01-01", periods=5, freq="min")
        df = pd.DataFrame({"time": times, "price": range(5)})
        result = compare_intraday_shape(df, df.copy())
        assert result["provider_a_time_monotonic"] is True


# ---------------------------------------------------------------------------
# compare_coverage
# ---------------------------------------------------------------------------


class TestCompareCoverage:
    def test_full_overlap(self):
        df = make_ohlcv(5, "2024-01-01")
        result = compare_coverage(df, df.copy())
        assert result["overlap_rows"] == 5

    def test_no_overlap(self):
        df_a = make_ohlcv(3, "2024-01-01")
        df_b = make_ohlcv(3, "2024-02-01")
        result = compare_coverage(df_a, df_b)
        assert result["overlap_rows"] == 0

    def test_raises_on_missing_time_col(self):
        df = pd.DataFrame({"price": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            compare_coverage(df, make_ohlcv())


# ---------------------------------------------------------------------------
# compare_freshness
# ---------------------------------------------------------------------------


class TestCompareFreshness:
    def test_equal_freshness(self):
        df = make_ohlcv(3)
        result = compare_freshness(df, df.copy())
        assert result["fresher_provider"] == "equal"
        assert result["staleness_delta_seconds"] == pytest.approx(0.0)

    def test_a_is_fresher(self):
        df_a = make_ohlcv(5, "2024-01-01")
        df_b = make_ohlcv(3, "2024-01-01")
        result = compare_freshness(df_a, df_b)
        assert result["fresher_provider"] == "provider_a"
        assert result["staleness_delta_seconds"] > 0

    def test_b_is_fresher(self):
        df_a = make_ohlcv(3, "2024-01-01")
        df_b = make_ohlcv(5, "2024-01-01")
        result = compare_freshness(df_a, df_b)
        assert result["fresher_provider"] == "provider_b"
        assert result["staleness_delta_seconds"] < 0

    def test_raises_on_missing_col(self):
        df = pd.DataFrame({"price": [1, 2]})
        with pytest.raises(ValueError):
            compare_freshness(df, make_ohlcv())
