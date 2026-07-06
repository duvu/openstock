"""Tests for vnstock.core.quality.validators.price_board."""

import pandas as pd

from vnstock.core.quality.validators.price_board import PriceBoardValidator

_VALIDATOR = PriceBoardValidator()


def _make_board(**overrides) -> pd.DataFrame:
    data = {
        "symbol": ["FPT", "VNM", "HPG"],
        "reference_price": [70_000.0, 80_000.0, 25_000.0],
        "close_price": [71_000.0, 81_000.0, 25_500.0],
        "volume_accumulated": [100_000, 200_000, 300_000],
        "ceiling_price": [77_000.0, 88_000.0, 27_500.0],
        "floor_price": [63_000.0, 72_000.0, 22_500.0],
        "bid_price_1": [70_500.0, 80_500.0, 25_200.0],
        "ask_price_1": [71_000.0, 81_000.0, 25_600.0],
        "bid_vol_1": [500, 1000, 200],
        "ask_vol_1": [300, 800, 400],
    }
    data.update(overrides)
    return pd.DataFrame(data)


class TestPriceBoardValidatorValidData:
    def test_valid_dataframe_no_errors(self):
        df = _make_board()
        report = _VALIDATOR.validate(df)
        assert report.valid is True
        assert report.errors == []

    def test_report_metadata(self):
        df = _make_board()
        report = _VALIDATOR.validate(df, provider="VCI", symbol=None, interval=None)
        assert report.dataset_type == "price_board"
        assert report.row_count == 3


class TestPriceBoardValidatorSchemaErrors:
    def test_missing_required_column(self):
        df = _make_board()
        df = df.drop(columns=["close_price"])
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "SCHEMA_MISSING_COLUMN" in codes
        assert report.valid is False

    def test_empty_dataframe(self):
        df = _make_board().iloc[0:0]
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "SCHEMA_EMPTY_DATAFRAME" in codes


class TestPriceBoardValidatorDuplicateSymbols:
    def test_duplicate_symbol_warning(self):
        df = _make_board()
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # duplicate FPT
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.warnings]
        assert "BOARD_DUPLICATE_SYMBOL" in codes


class TestPriceBoardValidatorPriceBand:
    def test_close_outside_ceiling(self):
        df = _make_board()
        df.loc[0, "close_price"] = 999_999.0  # way above ceiling
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "BOARD_PRICE_OUTSIDE_FLOOR_CEILING" in codes

    def test_floor_above_ceiling(self):
        df = _make_board()
        df.loc[0, "floor_price"] = 999_999.0
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "BOARD_PRICE_OUTSIDE_FLOOR_CEILING" in codes


class TestPriceBoardValidatorBidAsk:
    def test_bid_ask_crossed(self):
        df = _make_board()
        df.loc[0, "bid_price_1"] = 90_000.0  # bid > ask
        df.loc[0, "ask_price_1"] = 70_000.0
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.warnings]
        assert "BOARD_BID_ASK_CROSSED" in codes


class TestPriceBoardValidatorVolumes:
    def test_negative_bid_volume(self):
        df = _make_board()
        df.loc[0, "bid_vol_1"] = -100
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "BOARD_NEGATIVE_BID_VOLUME" in codes

    def test_negative_ask_volume(self):
        df = _make_board()
        df.loc[0, "ask_vol_1"] = -50
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "BOARD_NEGATIVE_ASK_VOLUME" in codes
