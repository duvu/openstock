"""Tests for vnstock.core.quality.registry."""

import pandas as pd
import pytest

from vnstock.core.quality.registry import (
    _REGISTRY,
    get_validator,
    register,
    validate_dataframe,
)


class TestRegistryDefaults:
    def test_ohlcv_registered(self):
        assert "ohlcv" in _REGISTRY

    def test_price_board_registered(self):
        assert "price_board" in _REGISTRY

    def test_intraday_registered(self):
        assert "intraday_trades" in _REGISTRY

    def test_get_validator_known_type(self):
        v = get_validator("ohlcv")
        assert v is not None

    def test_get_validator_unknown_type(self):
        v = get_validator("__nonexistent__")
        assert v is None


class TestValidateDataframe:
    def test_unsupported_dataset_type_raises(self):
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(ValueError, match="No validator registered"):
            validate_dataframe(df, dataset_type="__unknown__")

    def test_ohlcv_dispatch(self):
        df = pd.DataFrame(
            {
                "time": pd.date_range("2025-01-01", periods=3, freq="D"),
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [95.0, 96.0, 97.0],
                "close": [102.0, 103.0, 104.0],
                "volume": [1000, 2000, 3000],
            }
        )
        report = validate_dataframe(
            df, dataset_type="ohlcv", provider="TEST", symbol="FPT"
        )
        assert report.dataset_type == "ohlcv"
        assert report.valid is True

    def test_price_board_dispatch(self):
        df = pd.DataFrame(
            {
                "symbol": ["FPT"],
                "reference_price": [70_000.0],
                "close_price": [71_000.0],
                "volume_accumulated": [100_000],
            }
        )
        report = validate_dataframe(df, dataset_type="price_board")
        assert report.dataset_type == "price_board"

    def test_intraday_dispatch(self):
        df = pd.DataFrame(
            {
                "time": ["09:30:00"],
                "price": [70_000.0],
                "volume": [100],
                "match_type": ["buy"],
                "id": ["T001"],
            }
        )
        report = validate_dataframe(df, dataset_type="intraday_trades")
        assert report.dataset_type == "intraday_trades"


class TestCustomRegistration:
    def test_register_custom_validator(self):
        from vnstock.core.quality.base import BaseValidator
        from vnstock.core.quality.models import ValidationReport

        class DummyValidator(BaseValidator):
            dataset_type = "dummy_test_type"

            def validate(self, df, **kwargs):
                return ValidationReport(
                    valid=True,
                    dataset_type=self.dataset_type,
                    provider=None,
                    symbol=None,
                    interval=None,
                    row_count=len(df),
                    latest_time=None,
                    freshness_status="unknown",
                )

        register(DummyValidator())
        assert "dummy_test_type" in _REGISTRY
        df = pd.DataFrame({"x": [1]})
        report = validate_dataframe(df, dataset_type="dummy_test_type")
        assert report.valid is True
        # Cleanup
        del _REGISTRY["dummy_test_type"]
