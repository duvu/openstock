"""Contract tests for KBS provider adapter.

These tests verify that the KBS adapter can parse stored raw fixtures
and produce normalized DataFrames with expected schemas.

They do NOT call any live provider endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "providers" / "kbs"

_OHLCV_REQUIRED_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
_INTRADAY_REQUIRED_COLUMNS = ["time", "price", "volume"]

pytestmark = pytest.mark.contract


def _load_fixture(name: str):
    path = _FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestKBSOHLCVContract:
    """Verify KBS OHLCV raw fixture parses to expected normalized schema."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        assert isinstance(data, dict)
        assert "data_day" in data

    def test_raw_fixture_has_rows(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        rows = data["data_day"]
        assert len(rows) > 0
        row = rows[0]
        assert "t" in row
        assert "o" in row
        assert "c" in row
        assert "v" in row

    def test_fixture_parses_to_ohlcv_dataframe(self):
        """KBS adapter should convert raw fixture to normalized OHLCV DataFrame."""
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.kbs.quote.send_request", return_value=data):
            from vnstock.explorer.kbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert isinstance(df, pd.DataFrame)
        for col in _OHLCV_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_normalized_ohlcv_dtypes(self):
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.kbs.quote.send_request", return_value=data):
            from vnstock.explorer.kbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert df["time"].dtype.name.startswith("datetime"), (
            f"time dtype should be datetime, got {df['time'].dtype}"
        )
        assert df["open"].dtype == "float64"
        assert df["close"].dtype == "float64"

    def test_normalized_ohlcv_no_empty_rows(self):
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.kbs.quote.send_request", return_value=data):
            from vnstock.explorer.kbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert len(df) > 0

    def test_ohlcv_column_names_match_standard(self):
        """KBS raw keys (t/o/h/l/c/v) must map to standard column names."""
        data = _load_fixture("ohlcv_daily_raw.json")

        with patch("vnstock.explorer.kbs.quote.send_request", return_value=data):
            from vnstock.explorer.kbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        # Raw keys must not appear after rename
        raw_keys = {"t", "o", "h", "l", "c"}
        overlap = raw_keys & set(df.columns)
        assert overlap == set(), f"Raw keys still present after rename: {overlap}"


class TestKBSIntradayContract:
    """Verify KBS intraday raw fixture structure and parse."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("intraday_raw.json")
        assert isinstance(data, dict)
        assert "data" in data

    def test_raw_fixture_has_required_fields(self):
        data = _load_fixture("intraday_raw.json")
        rows = data["data"]
        assert len(rows) > 0
        row = rows[0]
        # KBS uses short codes: FMP=price, FV=match_volume, FT=time
        assert "FMP" in row
        assert "FV" in row
        assert "FT" in row

    def test_fixture_parses_to_intraday_dataframe(self):
        """KBS intraday adapter parses raw fixture to DataFrame."""
        data = _load_fixture("intraday_raw.json")

        with patch("vnstock.explorer.kbs.quote.send_request", return_value=data):
            from vnstock.explorer.kbs.quote import Quote

            q = Quote("FPT")
            df = q.intraday(page_size=100)

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        # KBS intraday produces: time, price, match_volume (at minimum)
        for col in _INTRADAY_REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_intraday_no_raw_keys_in_output(self):
        """KBS raw intraday codes must not appear in output DataFrame."""
        data = _load_fixture("intraday_raw.json")

        with patch("vnstock.explorer.kbs.quote.send_request", return_value=data):
            from vnstock.explorer.kbs.quote import Quote

            q = Quote("FPT")
            df = q.intraday(page_size=100)

        raw_codes = {"FMP", "FV", "FT", "LC", "SB", "TD"}
        overlap = raw_codes & set(df.columns)
        assert overlap == set(), f"Raw KBS codes still in output: {overlap}"


class TestKBSPriceBoardContract:
    """Verify KBS price board raw fixture structure."""

    def test_raw_fixture_loads(self):
        data = _load_fixture("price_board_raw.json")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_raw_fixture_has_required_fields(self):
        data = _load_fixture("price_board_raw.json")
        item = data[0]
        # KBS price board: SB=symbol, CP=close, FL=floor, CE=ceiling, RE=reference
        assert "SB" in item or "symbol" in item
        assert "CP" in item or "close_price" in item


class TestKBSContractDoesNotCallNetwork:
    """Contract tests must not call live endpoints."""

    def test_no_network_call_for_ohlcv(self):
        data = _load_fixture("ohlcv_daily_raw.json")
        call_count = 0

        def fake_send(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return data

        with patch("vnstock.explorer.kbs.quote.send_request", fake_send):
            from vnstock.explorer.kbs.quote import Quote

            q = Quote("FPT")
            df = q.history(start="2026-06-01", end="2026-07-02", interval="1D")

        assert call_count == 1
        assert len(df) > 0
