"""Contract tests for VCI provider adapter.

These tests verify that the VCI adapter can parse stored raw fixtures
and produce normalized DataFrames with expected schemas.

They do NOT call any live provider endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "providers" / "vci"

_OHLCV_REQUIRED_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
_INTRADAY_REQUIRED_COLUMNS = ["time", "price", "volume", "match_type"]

pytestmark = pytest.mark.contract


def _load_fixture(name: str):
    path = _FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestVCIOHLCVContract:
    """Verify VCI OHLCV raw fixture parses to expected normalized schema."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        # VCI returns list of objects with array fields
        assert isinstance(data, list)
        assert len(data) > 0

    def test_raw_fixture_array_format(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        item = data[0]
        assert "t" in item
        assert "o" in item
        assert "c" in item
        assert "v" in item
        assert isinstance(item["t"], list), "VCI 't' field should be a list"
        assert isinstance(item["o"], list), "VCI 'o' field should be a list"

    def test_fixture_parses_to_ohlcv_dataframe(self):
        """VCI adapter should convert raw array-format fixture to normalized DataFrame."""
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.vci.quote.send_request", return_value=data):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert isinstance(df, pd.DataFrame)
        for col in _OHLCV_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_normalized_ohlcv_dtypes(self):
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.vci.quote.send_request", return_value=data):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert df["time"].dtype.name.startswith("datetime"), (
            f"time dtype should be datetime, got {df['time'].dtype}"
        )
        assert df["open"].dtype == "float64"
        assert df["close"].dtype == "float64"

    def test_normalized_ohlcv_no_empty_rows(self):
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.vci.quote.send_request", return_value=data):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert len(df) > 0

    def test_ohlcv_column_names_match_standard(self):
        """VCI raw keys (t/o/h/l/c/v) must map to standard column names."""
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.vci.quote.send_request", return_value=data):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        raw_keys = {"t", "o", "h", "l", "c"}
        overlap = raw_keys & set(df.columns)
        assert overlap == set(), f"Raw keys still present after rename: {overlap}"


class TestVCIIntradayContract:
    """Verify VCI intraday raw fixture parses to expected normalized schema."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("intraday_raw.json")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_raw_fixture_has_required_fields(self):
        data = _load_fixture("intraday_raw.json")
        item = data[0]
        # VCI uses: truncTime, matchPrice, matchVol, matchType, id
        assert "truncTime" in item
        assert "matchPrice" in item
        assert "matchVol" in item
        assert "matchType" in item

    def test_fixture_parses_to_intraday_dataframe(self):
        """VCI intraday adapter should parse raw fixture to normalized DataFrame."""
        data = _load_fixture("intraday_raw.json")

        with patch("vnstock.explorer.vci.quote.send_request", return_value=data):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.intraday(page_size=100)

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        for col in _INTRADAY_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_intraday_no_raw_keys_in_output(self):
        """VCI raw intraday field names must not appear in output DataFrame."""
        data = _load_fixture("intraday_raw.json")

        with patch("vnstock.explorer.vci.quote.send_request", return_value=data):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.intraday(page_size=100)

        raw_keys = {"truncTime", "matchPrice", "matchVol", "matchType"}
        overlap = raw_keys & set(df.columns)
        assert overlap == set(), f"Raw field names still in output: {overlap}"

    def test_intraday_match_type_values(self):
        """match_type values in normalized output should be non-empty strings."""
        data = _load_fixture("intraday_raw.json")

        with patch("vnstock.explorer.vci.quote.send_request", return_value=data):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.intraday(page_size=100)

        assert df["match_type"].notna().all()
        assert (df["match_type"].astype(str).str.len() > 0).all()


class TestVCIPriceBoardContract:
    """Verify VCI price board raw fixture structure."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("price_board_raw.json")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_raw_fixture_has_required_fields(self):
        data = _load_fixture("price_board_raw.json")
        item = data[0]
        # VCI nested structure: listingInfo, matchPrice, bidAsk
        assert "listingInfo" in item or "symbol" in item or "s" in item
        assert "matchPrice" in item or "close_price" in item


class TestVCIContractDoesNotCallNetwork:
    """Contract tests must not call live endpoints."""

    def test_no_network_call_for_ohlcv(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        call_count = 0

        def fake_send(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return data

        with patch("vnstock.explorer.vci.quote.send_request", fake_send):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert call_count == 1
        assert len(df) > 0

    def test_no_network_call_for_intraday(self):
        data = _load_fixture("intraday_raw.json")
        call_count = 0

        def fake_send(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return data

        with patch("vnstock.explorer.vci.quote.send_request", fake_send):
            from vnstock.explorer.vci.quote import Quote

            q = Quote("FPT")
            df = q.intraday(page_size=100)

        assert call_count == 1
        assert len(df) > 0
