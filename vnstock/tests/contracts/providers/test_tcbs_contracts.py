"""Contract tests for TCBS provider adapter.

These tests verify that the TCBS adapter can parse stored raw fixtures
and produce normalized DataFrames with expected schemas.

They do NOT call any live provider endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "providers" / "tcbs"

_OHLCV_REQUIRED_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
_PRICE_BOARD_REQUIRED_COLUMNS = [
    "symbol",
    "close_price",
    "volume_accumulated",
]
_INTRADAY_REQUIRED_COLUMNS = ["time", "price", "volume", "match_type"]
_COMPANY_OVERVIEW_REQUIRED_COLUMNS = [
    "symbol",
    "exchange",
    "industry",
]
_FINANCIAL_REQUIRED_COLUMNS = [
    "symbol",
    "period_type",
    "report_type",
    "provider",
]


def _load_fixture(name: str):
    path = _FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


pytestmark = pytest.mark.contract


class TestTCBSOHLCVContract:
    """Verify TCBS OHLCV raw fixture parses to expected normalized schema."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        assert isinstance(data, dict)
        assert "data" in data
        assert len(data["data"]) > 0

    def test_raw_fixture_records_have_required_fields(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        record = data["data"][0]
        assert "t" in record
        assert "o" in record
        assert "h" in record
        assert "l" in record
        assert "c" in record
        assert "v" in record

    def test_fixture_parses_to_ohlcv_dataframe(self):
        """TCBS adapter should convert raw fixture to normalized OHLCV DataFrame."""
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.tcbs.quote.send_request", return_value=data):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert isinstance(df, pd.DataFrame)
        for col in _OHLCV_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_normalized_ohlcv_dtypes(self):
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.tcbs.quote.send_request", return_value=data):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert df["time"].dtype.name.startswith("datetime"), (
            f"time dtype should be datetime, got {df['time'].dtype}"
        )
        assert df["open"].dtype == "float64"
        assert df["close"].dtype == "float64"
        assert df["volume"].dtype == "int64"

    def test_normalized_ohlcv_not_empty(self):
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.tcbs.quote.send_request", return_value=data):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert len(df) > 0

    def test_ohlcv_metadata_attrs_set(self):
        """DataFrame attrs should have source, symbol, interval, endpoint_variant."""
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.tcbs.quote.send_request", return_value=data):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert df.attrs.get("source") == "TCBS"
        assert df.attrs.get("symbol") == "FPT"
        assert df.attrs.get("interval") == "1D"
        assert "endpoint_variant" in df.attrs

    def test_fallback_endpoint_used_on_primary_failure(self):
        """If primary endpoint fails, adapter tries fallback endpoints."""
        data = _load_fixture("ohlcv_daily_raw.json")
        call_count = 0

        def fake_send_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            url = args[0] if args else kwargs.get("url", "")
            if "stock/v2" in url:
                return None  # Simulate primary failure
            return data

        with patch("vnstock.explorer.tcbs.quote.send_request", fake_send_request):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert call_count > 1, "Should have tried multiple endpoints"
        assert len(df) > 0

    def test_all_endpoints_failed_raises_value_error(self):
        """ValueError raised when all endpoints return empty."""
        with patch("vnstock.explorer.tcbs.quote.send_request", return_value=None):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            with pytest.raises(ValueError, match="Không tìm thấy dữ liệu"):
                q.history(start="2026-06-01", end="2026-07-02", interval="1D")


class TestTCBSPriceBoardContract:
    """Verify TCBS price board raw fixture has expected structure."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("price_board_raw.json")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_raw_fixture_has_required_fields(self):
        data = _load_fixture("price_board_raw.json")
        item = data[0]
        assert "t" in item  # symbol (ticker field)
        assert "cp" in item  # close_price

    def test_normalized_schema_has_required_columns(self):
        """Parsed TCBS price board must include minimum required columns."""
        data = _load_fixture("price_board_raw.json")

        with patch("vnstock.explorer.tcbs.trading.send_request", return_value=data):
            from vnstock.explorer.tcbs.trading import Trading

            t = Trading()
            df = t.price_board(symbols_list=["FPT", "VCB"])

        for col in _PRICE_BOARD_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing price board column: {col}"

    def test_price_board_metadata_set(self):
        data = _load_fixture("price_board_raw.json")

        with patch("vnstock.explorer.tcbs.trading.send_request", return_value=data):
            from vnstock.explorer.tcbs.trading import Trading

            t = Trading()
            df = t.price_board(symbols_list=["FPT", "VCB"])

        assert df.attrs.get("source") == "TCBS"
        assert df.attrs.get("symbols") == ["FPT", "VCB"]

    def test_empty_symbols_list_raises(self):
        from vnstock.explorer.tcbs.trading import Trading

        t = Trading()
        with pytest.raises(ValueError, match="symbols_list không được để trống"):
            t.price_board(symbols_list=[])


class TestTCBSIntradayContract:
    """Verify TCBS intraday raw fixture structure."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("intraday_raw.json")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_raw_fixture_has_required_fields(self):
        data = _load_fixture("intraday_raw.json")
        item = data[0]
        assert "p" in item or "price" in item
        assert "v" in item or "volume" in item
        assert "a" in item  # match type field

    def test_match_type_normalized(self):
        """match_type 'BU'/'SD' should be normalized to 'buy'/'sell'."""
        data = _load_fixture("intraday_raw.json")

        with patch("vnstock.explorer.tcbs.quote.send_request", return_value=data):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            df = q.intraday()

        assert "match_type" in df.columns
        valid_values = {"buy", "sell", "unknown"}
        for v in df["match_type"].unique():
            assert v in valid_values, f"Unexpected match_type value: {v}"

    def test_empty_response_returns_empty_dataframe(self):
        with patch("vnstock.explorer.tcbs.quote.send_request", return_value=None):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            df = q.intraday()

        assert isinstance(df, pd.DataFrame)
        assert df.empty


class TestTCBSCompanyContract:
    """Verify TCBS Company adapter parses overview fixture correctly."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("company_overview_raw.json")
        assert isinstance(data, dict)
        assert "ticker" in data or "symbol" in data

    def test_overview_produces_normalized_dataframe(self):
        data = _load_fixture("company_overview_raw.json")

        # Both ticker and company endpoints called — mock both
        with patch("vnstock.explorer.tcbs.company.send_request", return_value=data):
            from vnstock.explorer.tcbs.company import Company

            c = Company("FPT")
            df = c.overview()

        assert isinstance(df, pd.DataFrame)
        for col in _COMPANY_OVERVIEW_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing company overview column: {col}"

    def test_overview_symbol_set_correctly(self):
        data = _load_fixture("company_overview_raw.json")

        with patch("vnstock.explorer.tcbs.company.send_request", return_value=data):
            from vnstock.explorer.tcbs.company import Company

            c = Company("FPT")
            df = c.overview()

        assert df.iloc[0]["symbol"] == "FPT"

    def test_overview_without_symbol_raises(self):
        from vnstock.explorer.tcbs.company import Company

        c = Company()
        with pytest.raises(ValueError, match="symbol"):
            c.overview()


class TestTCBSFinanceContract:
    """Verify TCBS Finance adapter parses balance sheet fixture correctly."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("financial_balance_sheet_raw.json")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_balance_sheet_normalized_metadata(self):
        """Balance sheet must have metadata columns: symbol, period_type, report_type, provider."""
        data = _load_fixture("financial_balance_sheet_raw.json")

        with patch("vnstock.explorer.tcbs.financial.send_request", return_value=data):
            from vnstock.explorer.tcbs.financial import Finance

            f = Finance("FPT", period="quarter")
            df = f.balance_sheet()

        assert isinstance(df, pd.DataFrame)
        for col in _FINANCIAL_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing financial column: {col}"
        assert df.iloc[0]["symbol"] == "FPT"
        assert df.iloc[0]["provider"] == "TCBS"
        assert df.iloc[0]["period_type"] == "quarter"

    def test_invalid_period_raises(self):
        from vnstock.explorer.tcbs.financial import Finance

        with pytest.raises(ValueError, match="year.*quarter"):
            Finance("FPT", period="monthly")

    def test_empty_response_returns_empty_dataframe(self):
        with patch("vnstock.explorer.tcbs.financial.send_request", return_value=None):
            from vnstock.explorer.tcbs.financial import Finance

            f = Finance("FPT", period="quarter")
            df = f.balance_sheet()

        assert isinstance(df, pd.DataFrame)
        assert df.empty


class TestTCBSContractDoesNotCallNetwork:
    """Contract tests must not call live endpoints."""

    def test_no_network_call_for_ohlcv(self):
        """Verify test does not make a real HTTP call."""
        data = _load_fixture("ohlcv_daily_raw.json")
        call_count = 0

        def fake_send_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return data

        with patch("vnstock.explorer.tcbs.quote.send_request", fake_send_request):
            from vnstock.explorer.tcbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert call_count == 1, (
            f"Should have called mocked send_request exactly once, got {call_count}"
        )
        assert len(df) > 0

    def test_no_network_call_for_price_board(self):
        data = _load_fixture("price_board_raw.json")
        call_count = 0

        def fake_send_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return data

        with patch("vnstock.explorer.tcbs.trading.send_request", fake_send_request):
            from vnstock.explorer.tcbs.trading import Trading

            t = Trading()
            df = t.price_board(symbols_list=["FPT"])

        assert call_count == 1
        assert not df.empty
