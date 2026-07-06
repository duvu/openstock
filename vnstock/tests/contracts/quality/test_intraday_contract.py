"""Provider contract tests for intraday trade validators.

These tests use static sample DataFrames that represent typical provider
output shapes. They do NOT call any external API.
"""

import pandas as pd

from vnstock.core.quality.registry import validate_dataframe


def _sample_intraday_trades() -> pd.DataFrame:
    """Typical intraday trades for FPT from a VCI/DNSE provider."""
    return pd.DataFrame(
        {
            "time": ["09:15:01", "09:16:02", "09:17:03", "09:18:04", "09:19:05"],
            "price": [75_000.0, 75_100.0, 74_900.0, 75_200.0, 75_300.0],
            "volume": [100, 200, 150, 300, 250],
            "match_type": ["buy", "sell", "buy", "atc", "buy"],
            "id": ["T001", "T002", "T003", "T004", "T005"],
        }
    )


class TestIntradayContract:
    def test_valid_sample(self):
        df = _sample_intraday_trades()
        report = validate_dataframe(
            df, dataset_type="intraday_trades", provider="VCI", symbol="FPT"
        )
        assert report.valid is True, (
            f"Unexpected errors: {[e.code for e in report.errors]}"
        )

    def test_no_duplicate_ids(self):
        df = _sample_intraday_trades()
        report = validate_dataframe(df, dataset_type="intraday_trades")
        dup_issues = [i for i in report.warnings if i.code == "TRADE_DUPLICATE_ID"]
        assert dup_issues == []

    def test_valid_match_types(self):
        df = _sample_intraday_trades()
        report = validate_dataframe(df, dataset_type="intraday_trades")
        mt_errors = [e for e in report.errors if e.code == "TRADE_INVALID_MATCH_TYPE"]
        assert mt_errors == []

    def test_positive_prices(self):
        df = _sample_intraday_trades()
        report = validate_dataframe(df, dataset_type="intraday_trades")
        price_errors = [
            e for e in report.errors if e.code == "TRADE_NON_POSITIVE_PRICE"
        ]
        assert price_errors == []


class TestIntradayContractErrorDetection:
    def test_invalid_match_type_detected(self):
        df = _sample_intraday_trades()
        df.loc[2, "match_type"] = "unknown_type"
        report = validate_dataframe(df, dataset_type="intraday_trades")
        assert any(e.code == "TRADE_INVALID_MATCH_TYPE" for e in report.errors)

    def test_duplicate_id_detected(self):
        df = _sample_intraday_trades()
        df.loc[3, "id"] = "T001"
        report = validate_dataframe(df, dataset_type="intraday_trades")
        assert any(
            i.code == "TRADE_DUPLICATE_ID" for i in report.warnings + report.errors
        )

    def test_zero_price_detected(self):
        df = _sample_intraday_trades()
        df.loc[0, "price"] = 0.0
        report = validate_dataframe(df, dataset_type="intraday_trades")
        assert any(e.code == "TRADE_NON_POSITIVE_PRICE" for e in report.errors)
