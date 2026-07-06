"""Provider contract tests for price board validators.

These tests use static sample DataFrames that represent typical provider
output shapes. They do NOT call any external API.
"""

import pandas as pd

from vnstock.core.quality.registry import validate_dataframe


def _sample_price_board() -> pd.DataFrame:
    """Typical price board snapshot for VCI/KBS/DNSE."""
    return pd.DataFrame(
        {
            "symbol": ["FPT", "VNM", "HPG", "VIC"],
            "reference_price": [74_900.0, 82_000.0, 27_500.0, 45_000.0],
            "close_price": [75_200.0, 82_500.0, 27_800.0, 44_800.0],
            "volume_accumulated": [500_000, 200_000, 1_200_000, 800_000],
            "ceiling_price": [82_400.0, 90_200.0, 30_200.0, 49_500.0],
            "floor_price": [67_400.0, 73_800.0, 24_800.0, 40_500.0],
            "bid_price_1": [75_000.0, 82_300.0, 27_700.0, 44_700.0],
            "ask_price_1": [75_300.0, 82_600.0, 27_900.0, 44_900.0],
            "bid_vol_1": [1000, 500, 2000, 800],
            "ask_vol_1": [800, 700, 1800, 1000],
        }
    )


class TestPriceBoardContract:
    def test_valid_sample(self):
        df = _sample_price_board()
        report = validate_dataframe(df, dataset_type="price_board", provider="VCI")
        assert report.valid is True, (
            f"Unexpected errors: {[e.code for e in report.errors]}"
        )

    def test_no_duplicate_symbols(self):
        df = _sample_price_board()
        report = validate_dataframe(df, dataset_type="price_board")
        dup_issues = [i for i in report.warnings if i.code == "BOARD_DUPLICATE_SYMBOL"]
        assert dup_issues == []

    def test_bid_ask_not_crossed(self):
        df = _sample_price_board()
        report = validate_dataframe(df, dataset_type="price_board")
        crossed = [i for i in report.warnings if i.code == "BOARD_BID_ASK_CROSSED"]
        assert crossed == []

    def test_prices_within_band(self):
        df = _sample_price_board()
        report = validate_dataframe(df, dataset_type="price_board")
        band_errors = [
            e for e in report.errors if e.code == "BOARD_PRICE_OUTSIDE_FLOOR_CEILING"
        ]
        assert band_errors == []


class TestPriceBoardContractErrorDetection:
    def test_duplicate_symbol_detected(self):
        df = _sample_price_board()
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        report = validate_dataframe(df, dataset_type="price_board")
        assert any(
            i.code == "BOARD_DUPLICATE_SYMBOL" for i in report.warnings + report.errors
        )

    def test_close_outside_ceiling_detected(self):
        df = _sample_price_board()
        df.loc[0, "close_price"] = 999_999.0
        report = validate_dataframe(df, dataset_type="price_board")
        assert any(e.code == "BOARD_PRICE_OUTSIDE_FLOOR_CEILING" for e in report.errors)
