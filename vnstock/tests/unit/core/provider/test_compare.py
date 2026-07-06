"""Tests for cross-provider comparison (vnstock/core/provider/compare.py)."""

from __future__ import annotations

import pandas as pd

from vnstock.core.provider.compare import compare_ohlcv


def _make_ohlcv(
    dates: list[str],
    close_values: list[float],
    volume_values: list[int],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.to_datetime(dates),
            "open": close_values,
            "high": [v * 1.01 for v in close_values],
            "low": [v * 0.99 for v in close_values],
            "close": close_values,
            "volume": volume_values,
        }
    )


_DATES = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"]


class TestCompareOHLCVInsufficientProviders:
    """Need at least 2 providers."""

    def test_single_provider_not_comparable(self):
        df = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        report = compare_ohlcv({"vci": df}, symbol="FPT")
        assert report.comparable is False
        assert any(i.code == "COMPARE_INSUFFICIENT_PROVIDERS" for i in report.issues)

    def test_empty_providers_not_comparable(self):
        report = compare_ohlcv({}, symbol="FPT")
        assert report.comparable is False


class TestCompareOHLCVIdentical:
    """Two identical DataFrames should produce no issues."""

    def test_identical_dfs_no_issues(self):
        df = _make_ohlcv(_DATES, [100.0, 101.0, 102.0, 101.0, 100.5], [1000] * 5)
        report = compare_ohlcv({"vci": df, "kbs": df.copy()}, symbol="FPT")
        assert report.issues == []
        assert report.comparable is True

    def test_identical_row_counts(self):
        df = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        report = compare_ohlcv({"vci": df, "kbs": df.copy()}, symbol="FPT")
        assert report.row_count_by_provider["vci"] == 5
        assert report.row_count_by_provider["kbs"] == 5


class TestCompareOHLCVPriceDivergence:
    """Price diff at/above thresholds should generate issues."""

    def test_small_diff_no_issue(self):
        df_a = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        df_b = _make_ohlcv(_DATES, [100.005] * 5, [1000] * 5)  # 0.005% diff
        report = compare_ohlcv({"vci": df_a, "kbs": df_b})
        assert not any(i.code.startswith("COMPARE_PRICE") for i in report.issues)

    def test_warn_threshold_triggers_warning(self):
        df_a = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        df_b = _make_ohlcv(_DATES, [101.5] * 5, [1000] * 5)  # 1.5% diff > 1% warn
        report = compare_ohlcv(
            {"vci": df_a, "kbs": df_b},
            price_warn_pct=0.01,
            price_error_pct=0.05,
        )
        codes = [i.code for i in report.issues]
        assert "COMPARE_PRICE_DIVERGENCE" in codes
        assert "COMPARE_PRICE_DIVERGENCE_HIGH" not in codes

    def test_error_threshold_triggers_error(self):
        df_a = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        df_b = _make_ohlcv(_DATES, [106.0] * 5, [1000] * 5)  # 6% diff > 5% error
        report = compare_ohlcv(
            {"vci": df_a, "kbs": df_b},
            price_warn_pct=0.01,
            price_error_pct=0.05,
        )
        codes = [i.code for i in report.issues]
        assert "COMPARE_PRICE_DIVERGENCE_HIGH" in codes

    def test_diff_summary_populated(self):
        df_a = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        df_b = _make_ohlcv(_DATES, [102.0] * 5, [1000] * 5)
        report = compare_ohlcv({"vci": df_a, "kbs": df_b})
        assert "vci_vs_kbs" in report.price_diff_summary
        summary = report.price_diff_summary["vci_vs_kbs"]
        assert summary["count"] == 5
        assert summary["max"] is not None


class TestCompareOHLCVVolumeDivergence:
    """Volume diff above threshold should generate warning."""

    def test_large_volume_diff_warns(self):
        df_a = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        df_b = _make_ohlcv(_DATES, [100.0] * 5, [1200] * 5)  # 20% vol diff
        report = compare_ohlcv(
            {"vci": df_a, "kbs": df_b},
            volume_warn_pct=0.10,
        )
        codes = [i.code for i in report.issues]
        assert "COMPARE_VOLUME_DIVERGENCE" in codes

    def test_small_volume_diff_no_issue(self):
        df_a = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        df_b = _make_ohlcv(_DATES, [100.0] * 5, [1005] * 5)  # 0.5% diff
        report = compare_ohlcv({"vci": df_a, "kbs": df_b}, volume_warn_pct=0.10)
        assert not any(i.code == "COMPARE_VOLUME_DIVERGENCE" for i in report.issues)


class TestCompareOHLCVCoverageGap:
    """Missing dates in one provider should generate COMPARE_COVERAGE_GAP."""

    def test_missing_dates_warn(self):
        df_a = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        # Provider B missing 3 of 5 dates = 60% coverage gap
        df_b = _make_ohlcv(_DATES[:2], [100.0] * 2, [1000] * 2)
        report = compare_ohlcv(
            {"vci": df_a, "kbs": df_b},
            coverage_warn_pct=0.20,
        )
        codes = [i.code for i in report.issues]
        assert "COMPARE_COVERAGE_GAP" in codes

    def test_missing_dates_tracked(self):
        df_a = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        df_b = _make_ohlcv(_DATES[:3], [100.0] * 3, [1000] * 3)
        report = compare_ohlcv({"vci": df_a, "kbs": df_b})
        assert "kbs" in report.missing_dates_by_provider
        assert len(report.missing_dates_by_provider["kbs"]) == 2

    def test_no_common_dates_error(self):
        dates_a = ["2026-06-01", "2026-06-02"]
        dates_b = ["2026-06-03", "2026-06-04"]
        df_a = _make_ohlcv(dates_a, [100.0] * 2, [1000] * 2)
        df_b = _make_ohlcv(dates_b, [100.0] * 2, [1000] * 2)
        report = compare_ohlcv({"vci": df_a, "kbs": df_b})
        codes = [i.code for i in report.issues]
        assert "COMPARE_NO_COMMON_DATES" in codes


class TestCompareOHLCVReportMetadata:
    """Report metadata is correctly populated."""

    def test_report_providers_list(self):
        df = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        report = compare_ohlcv(
            {"vci": df, "kbs": df.copy()},
            symbol="FPT",
            interval="1D",
            start="2026-06-01",
            end="2026-06-05",
        )
        assert set(report.providers) == {"vci", "kbs"}
        assert report.symbol == "FPT"
        assert report.interval == "1D"
        assert report.base_provider == "vci"

    def test_to_dict_serializable(self):
        df = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        report = compare_ohlcv({"vci": df, "kbs": df.copy()})
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "dataset_type" in d
        assert "issues" in d

    def test_to_json_string(self):
        df = _make_ohlcv(_DATES, [100.0] * 5, [1000] * 5)
        report = compare_ohlcv({"vci": df, "kbs": df.copy()})
        j = report.to_json()
        assert isinstance(j, str)
        assert "ohlcv" in j
