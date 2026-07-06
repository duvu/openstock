"""Tests for schema drift detection (vnstock/core/provider/drift.py)."""

from __future__ import annotations

import pandas as pd
import pytest

from vnstock.core.provider.drift import (
    ColumnSpec,
    DatasetSchema,
    detect_drift,
    get_baseline_schema,
    register_schema,
)


def _make_valid_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"]),
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000, 1200, 1100],
        }
    )


def _make_valid_intraday() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-06-01 09:15:30", "2026-06-01 09:16:00"]),
            "price": [118.0, 117.9],
            "volume": [500, 300],
            "match_type": ["buy", "sell"],
        }
    )


def _make_valid_price_board() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["FPT", "VCB"],
            "reference_price": [118.0, 90.0],
            "close_price": [119.0, 91.0],
            "volume_accumulated": [5000, 8000],
        }
    )


class TestDetectDriftNoIssues:
    """Valid DataFrames should produce zero issues."""

    def test_valid_ohlcv_no_drift(self):
        df = _make_valid_ohlcv()
        issues = detect_drift(df, "vci", "ohlcv")
        assert issues == [], f"Expected no issues, got: {issues}"

    def test_valid_ohlcv_kbs_no_drift(self):
        df = _make_valid_ohlcv()
        issues = detect_drift(df, "kbs", "ohlcv")
        assert issues == []

    def test_valid_ohlcv_dnse_no_drift(self):
        df = _make_valid_ohlcv()
        issues = detect_drift(df, "dnse", "ohlcv")
        assert issues == []

    def test_valid_ohlcv_tcbs_no_drift(self):
        df = _make_valid_ohlcv()
        issues = detect_drift(df, "tcbs", "ohlcv")
        assert issues == []

    def test_valid_intraday_no_drift(self):
        df = _make_valid_intraday()
        issues = detect_drift(df, "vci", "intraday_trades")
        assert issues == []

    def test_valid_price_board_no_drift(self):
        df = _make_valid_price_board()
        issues = detect_drift(df, "vci", "price_board")
        assert issues == []


class TestDetectDriftMissingColumn:
    """Missing required columns should produce DRIFT_MISSING_COLUMN error."""

    @pytest.mark.parametrize(
        "missing_col", ["time", "open", "high", "low", "close", "volume"]
    )
    def test_missing_ohlcv_column(self, missing_col):
        df = _make_valid_ohlcv().drop(columns=[missing_col])
        issues = detect_drift(df, "vci", "ohlcv")
        codes = [i.code for i in issues]
        assert "DRIFT_MISSING_COLUMN" in codes
        contexts = [i.context for i in issues if i.code == "DRIFT_MISSING_COLUMN"]
        assert any(c["column"] == missing_col for c in contexts)

    def test_missing_intraday_time_column(self):
        df = _make_valid_intraday().drop(columns=["time"])
        issues = detect_drift(df, "vci", "intraday_trades")
        assert any(i.code == "DRIFT_MISSING_COLUMN" for i in issues)

    def test_missing_price_board_symbol_column(self):
        df = _make_valid_price_board().drop(columns=["symbol"])
        issues = detect_drift(df, "vci", "price_board")
        assert any(i.code == "DRIFT_MISSING_COLUMN" for i in issues)


class TestDetectDriftDtypeMismatch:
    """Wrong dtype should produce DRIFT_DTYPE_MISMATCH issue."""

    def test_ohlcv_close_as_string_produces_drift(self):
        df = _make_valid_ohlcv().copy()
        df["close"] = df["close"].astype(str)
        issues = detect_drift(df, "vci", "ohlcv")
        codes = [i.code for i in issues]
        assert "DRIFT_DTYPE_MISMATCH" in codes

    def test_ohlcv_volume_as_float_produces_drift(self):
        df = _make_valid_ohlcv().copy()
        df["volume"] = df["volume"].astype(float)
        issues = detect_drift(df, "vci", "ohlcv")
        codes = [i.code for i in issues]
        assert "DRIFT_DTYPE_MISMATCH" in codes


class TestDetectDriftRowCount:
    """Row count violations should produce DRIFT_ROW_COUNT_* issues."""

    def test_empty_dataframe_produces_row_count_issue(self):
        df = _make_valid_ohlcv().iloc[0:0]  # empty
        issues = detect_drift(df, "vci", "ohlcv")
        assert any(i.code == "DRIFT_ROW_COUNT_LOW" for i in issues)

    def test_max_row_violation(self):
        custom_schema = DatasetSchema(
            dataset_type="ohlcv",
            provider="test",
            columns=list(get_baseline_schema("vci", "ohlcv").columns),
            min_rows=1,
            max_rows=2,
        )
        df = _make_valid_ohlcv()  # 3 rows
        issues = detect_drift(df, "test", "ohlcv", extra_schema=custom_schema)
        assert any(i.code == "DRIFT_ROW_COUNT_HIGH" for i in issues)


class TestDetectDriftNoBaseline:
    """Unknown provider/dataset returns DRIFT_NO_BASELINE info issue."""

    def test_unknown_provider_returns_info(self):
        df = _make_valid_ohlcv()
        issues = detect_drift(df, "unknown_provider", "ohlcv")
        assert len(issues) == 1
        assert issues[0].code == "DRIFT_NO_BASELINE"
        assert issues[0].severity == "info"

    def test_unknown_dataset_type_returns_info(self):
        df = _make_valid_ohlcv()
        issues = detect_drift(df, "vci", "unknown_dataset")
        assert len(issues) == 1
        assert issues[0].code == "DRIFT_NO_BASELINE"


class TestDetectDriftExtraSchema:
    """Caller-supplied schema takes precedence over built-in baselines."""

    def test_custom_schema_missing_column_detected(self):
        custom_schema = DatasetSchema(
            dataset_type="custom",
            provider="test",
            columns=[ColumnSpec("required_col", "float64")],
            min_rows=1,
        )
        df = pd.DataFrame({"other_col": [1.0, 2.0]})
        issues = detect_drift(df, "test", "custom", extra_schema=custom_schema)
        assert any(i.code == "DRIFT_MISSING_COLUMN" for i in issues)

    def test_custom_schema_no_issues(self):
        custom_schema = DatasetSchema(
            dataset_type="custom",
            provider="test",
            columns=[ColumnSpec("price", "float64")],
            min_rows=1,
        )
        df = pd.DataFrame({"price": [100.0, 101.0]})
        issues = detect_drift(df, "test", "custom", extra_schema=custom_schema)
        assert issues == []


class TestGetBaselineSchema:
    """get_baseline_schema returns correct schema or None."""

    def test_returns_schema_for_known_provider(self):
        schema = get_baseline_schema("vci", "ohlcv")
        assert schema is not None
        assert schema.provider == "vci"
        assert schema.dataset_type == "ohlcv"
        col_names = [c.name for c in schema.columns]
        assert "time" in col_names
        assert "close" in col_names

    def test_returns_none_for_unknown(self):
        schema = get_baseline_schema("nonexistent", "ohlcv")
        assert schema is None

    def test_case_insensitive(self):
        schema = get_baseline_schema("VCI", "ohlcv")
        assert schema is not None


class TestRegisterSchema:
    """register_schema allows custom schemas to be used by detect_drift."""

    def test_register_and_detect(self):
        custom = DatasetSchema(
            dataset_type="my_type",
            provider="my_provider",
            columns=[ColumnSpec("val", "float64")],
            min_rows=1,
        )
        register_schema(custom)

        df_valid = pd.DataFrame({"val": [1.0]})
        issues = detect_drift(df_valid, "my_provider", "my_type")
        assert issues == []

        df_bad = pd.DataFrame({"other": [1.0]})
        issues_bad = detect_drift(df_bad, "my_provider", "my_type")
        assert any(i.code == "DRIFT_MISSING_COLUMN" for i in issues_bad)
