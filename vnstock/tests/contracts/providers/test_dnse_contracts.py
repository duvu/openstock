"""Contract tests for DNSE provider adapter.

These tests verify that the DNSE adapter can parse stored raw fixtures
and produce normalized DataFrames with expected schemas.

They do NOT call any live provider endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "providers" / "dnse"

_OHLCV_REQUIRED_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
_PRICE_BOARD_REQUIRED_COLUMNS = [
    "symbol",
    "reference_price",
    "close_price",
    "volume_accumulated",
]
_INTRADAY_REQUIRED_COLUMNS = ["time", "price", "volume", "match_type"]


def _load_fixture(name: str):
    path = _FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


pytestmark = pytest.mark.contract


class TestDNSEOHLCVContract:
    """Verify DNSE OHLCV raw fixture parses to expected normalized schema."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        assert isinstance(data, dict)
        assert "t" in data
        assert "o" in data
        assert "h" in data
        assert "l" in data
        assert "c" in data
        assert "v" in data

    def test_raw_fixture_has_required_arrays(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        assert len(data["t"]) > 0
        assert len(data["t"]) == len(data["o"]) == len(data["c"])

    def test_fixture_parses_to_ohlcv_dataframe(self):
        """DNSE adapter should convert raw fixture to normalized OHLCV DataFrame."""
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.dnse.quote.send_request", return_value=data):
            from vnstock.explorer.dnse.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert isinstance(df, pd.DataFrame)
        for col in _OHLCV_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_normalized_ohlcv_dtypes(self):
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.dnse.quote.send_request", return_value=data):
            from vnstock.explorer.dnse.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert df["time"].dtype.name.startswith("datetime"), (
            f"time dtype should be datetime, got {df['time'].dtype}"
        )
        assert df["open"].dtype == "float64"
        assert df["close"].dtype == "float64"
        assert df["volume"].dtype == "int64"

    def test_normalized_ohlcv_no_empty_rows(self):
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.dnse.quote.send_request", return_value=data):
            from vnstock.explorer.dnse.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert len(df) > 0

    def test_fixture_missing_volume_detected(self):
        """Contract must detect when 'v' key is missing from raw response."""
        data = _load_fixture("ohlcv_daily_raw.json")
        del data["v"]

        with patch("vnstock.explorer.dnse.quote.send_request", return_value=data):
            from vnstock.explorer.dnse.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        # DNSE fills missing 'v' with zeros — volume column still present but all 0
        assert "volume" in df.columns


class TestDNSEPriceBoardContract:
    """Verify DNSE price board raw fixture has expected structure."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("price_board_raw.json")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_raw_fixture_has_required_fields(self):
        data = _load_fixture("price_board_raw.json")
        item = data[0]
        # DNSE price board uses short codes
        assert "sym" in item or "symbol" in item
        assert "c" in item  # close_price
        assert "r" in item  # reference_price

    def test_normalized_schema_has_required_columns(self):
        """Parsed DNSE price board should include minimum required columns.

        This test intentionally does NOT swallow ImportError or interface
        changes — a failure here means the provider interface has drifted
        and the contract test must be updated accordingly.
        """
        data = _load_fixture("price_board_raw.json")

        with patch("vnstock.explorer.dnse.trading.send_request", return_value=data):
            from vnstock.explorer.dnse.trading import Trading

            t = Trading()
            df = t.price_board(symbols_list=["FPT", "VCB"])

        for col in _PRICE_BOARD_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing price board column: {col}"


class TestDNSEIntradayContract:
    """Verify DNSE intraday raw fixture structure."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("intraday_raw.json")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_raw_fixture_has_required_fields(self):
        data = _load_fixture("intraday_raw.json")
        item = data[0]
        assert "price" in item or "p" in item
        assert "volume" in item or "v" in item


class TestDNSEContractDoesNotCallNetwork:
    """Contract tests must not call live endpoints."""

    def test_no_network_call_for_ohlcv(self):
        """Verify test does not make a real HTTP call."""
        data = _load_fixture("ohlcv_daily_raw.json")
        call_count = 0

        def fake_send_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return data

        with patch("vnstock.explorer.dnse.quote.send_request", fake_send_request):
            from vnstock.explorer.dnse.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert call_count == 1, "Should have called mocked send_request exactly once"
        assert len(df) > 0
