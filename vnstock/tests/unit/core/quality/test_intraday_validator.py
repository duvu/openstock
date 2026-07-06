"""Tests for vnstock.core.quality.validators.intraday."""

import pandas as pd

from vnstock.core.quality.validators.intraday import IntradayValidator

_VALIDATOR = IntradayValidator()


def _make_trades(**overrides) -> pd.DataFrame:
    data = {
        "time": ["09:30:00", "09:31:00", "09:32:00"],
        "price": [70_000.0, 70_500.0, 71_000.0],
        "volume": [100, 200, 300],
        "match_type": ["buy", "sell", "buy"],
        "id": ["T001", "T002", "T003"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


class TestIntradayValidatorValidData:
    def test_valid_trades_no_errors(self):
        df = _make_trades()
        report = _VALIDATOR.validate(df)
        assert report.valid is True
        assert report.errors == []

    def test_report_metadata(self):
        df = _make_trades()
        report = _VALIDATOR.validate(df, provider="VCI", symbol="FPT")
        assert report.dataset_type == "intraday_trades"
        assert report.row_count == 3


class TestIntradayValidatorSchemaErrors:
    def test_missing_required_column(self):
        df = _make_trades()
        df = df.drop(columns=["match_type"])
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "SCHEMA_MISSING_COLUMN" in codes
        assert report.valid is False

    def test_empty_dataframe(self):
        df = _make_trades().iloc[0:0]
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "SCHEMA_EMPTY_DATAFRAME" in codes


class TestIntradayValidatorMatchType:
    def test_invalid_match_type(self):
        df = _make_trades()
        df.loc[1, "match_type"] = "abc"
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "TRADE_INVALID_MATCH_TYPE" in codes
        assert report.valid is False

    def test_valid_all_match_types(self):
        for mt in ("buy", "sell", "unknown", "ato", "atc"):
            df = _make_trades(match_type=[mt, "buy", "sell"])
            report = _VALIDATOR.validate(df)
            err_codes = [i.code for i in report.errors]
            assert "TRADE_INVALID_MATCH_TYPE" not in err_codes


class TestIntradayValidatorDuplicateIds:
    def test_duplicate_id_warning(self):
        df = _make_trades()
        df.loc[2, "id"] = "T001"  # duplicate of row 0
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.warnings]
        assert "TRADE_DUPLICATE_ID" in codes


class TestIntradayValidatorPriceVolume:
    def test_non_positive_price(self):
        df = _make_trades()
        df.loc[0, "price"] = 0.0
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "TRADE_NON_POSITIVE_PRICE" in codes

    def test_negative_price(self):
        df = _make_trades()
        df.loc[0, "price"] = -100.0
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "TRADE_NON_POSITIVE_PRICE" in codes

    def test_negative_volume(self):
        df = _make_trades()
        df.loc[0, "volume"] = -10
        report = _VALIDATOR.validate(df)
        codes = [i.code for i in report.errors]
        assert "TRADE_NEGATIVE_VOLUME" in codes

    def test_zero_volume_is_allowed(self):
        df = _make_trades()
        df.loc[0, "volume"] = 0
        report = _VALIDATOR.validate(df)
        err_codes = [i.code for i in report.errors]
        assert "TRADE_NEGATIVE_VOLUME" not in err_codes
