"""
Live smoke tests for DNSE provider.

These tests call real DNSE endpoints and require network access.
They are disabled by default. Enable with:

    VNSTOCK_LIVE_TESTS=true pytest tests/live/providers/test_dnse_live.py -m live

Optional filtering:

    VNSTOCK_LIVE_SYMBOLS=FPT  # test a single symbol
"""

import pytest

from tests.live.conftest import LIVE_SYMBOLS, skip_if_provider_excluded

pytestmark = [pytest.mark.live, pytest.mark.provider, pytest.mark.provider_dnse]

_PROVIDER = "DNSE"

# Use only the first symbol to stay rate-limit friendly
_SYMBOL = LIVE_SYMBOLS[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_quote(symbol: str):
    from vnstock.explorer.dnse.quote import Quote

    return Quote(symbol=symbol)


def _get_trading():
    from vnstock.explorer.dnse.trading import Trading

    return Trading()


# ---------------------------------------------------------------------------
# OHLCV live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestDNSELiveOHLCV:
    """Verify DNSE OHLCV endpoint returns parseable, schema-valid data."""

    def test_history_returns_dataframe(self):
        """DNSE history() returns a non-empty DataFrame."""
        import pandas as pd

        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty, "DataFrame should not be empty"

    def test_history_has_ohlcv_columns(self):
        """DNSE history() output has required OHLCV columns."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        for col in ("time", "open", "high", "low", "close", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_history_numeric_prices(self):
        """DNSE OHLCV prices are positive finite numbers."""
        import numpy as np

        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        for col in ("open", "high", "low", "close"):
            assert (df[col] > 0).all(), f"Non-positive price in column {col}"
            assert np.isfinite(df[col]).all(), f"Non-finite price in column {col}"

    def test_history_no_raw_array_keys(self):
        """Normalized DNSE output does not expose raw array field names like 't', 'o'."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        raw_keys = {"t", "o", "h", "l", "c", "v"}
        leaked = raw_keys & set(df.columns)
        assert not leaked, f"Raw keys leaked into normalized output: {leaked}"


# ---------------------------------------------------------------------------
# Price board live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestDNSELivePriceBoard:
    """Verify DNSE price_board endpoint returns parseable, schema-valid data."""

    def test_price_board_returns_dataframe(self):
        """DNSE price_board() returns a non-empty DataFrame."""
        import pandas as pd

        t = _get_trading()
        df = t.price_board(symbols_list=[_SYMBOL])

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty, "DataFrame should not be empty"

    def test_price_board_has_symbol_column(self):
        """DNSE price_board() output contains a symbol identifier."""
        t = _get_trading()
        df = t.price_board(symbols_list=[_SYMBOL])

        symbol_cols = [c for c in df.columns if "symbol" in c.lower() or c == "sym"]
        assert symbol_cols, "No symbol column found in price_board output"

    def test_price_board_rate_limit_friendly(self):
        """DNSE price_board() can be called with a minimal symbol set."""
        t = _get_trading()
        # Only 1 symbol to avoid rate limit
        df = t.price_board(symbols_list=[_SYMBOL])
        assert df is not None


# ---------------------------------------------------------------------------
# Intraday live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestDNSELiveIntraday:
    """Verify DNSE intraday endpoint returns parseable, schema-valid data."""

    def test_intraday_returns_dataframe(self):
        """DNSE intraday() returns a DataFrame (may be empty on non-trading day)."""
        import pandas as pd

        q = _get_quote(_SYMBOL)
        df = q.intraday()

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"

    def test_intraday_has_expected_columns_when_nonempty(self):
        """DNSE intraday() has required columns if data is present."""
        q = _get_quote(_SYMBOL)
        df = q.intraday()

        if df.empty:
            pytest.skip("No intraday data (non-trading day or after hours)")

        for col in ("time", "price", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_intraday_no_raw_field_names(self):
        """Normalized DNSE intraday output does not expose raw field names."""
        q = _get_quote(_SYMBOL)
        df = q.intraday()

        if df.empty:
            pytest.skip("No intraday data (non-trading day or after hours)")

        raw_keys = {"seq", "side"}
        leaked = raw_keys & set(df.columns)
        assert not leaked, f"Raw keys leaked into normalized intraday output: {leaked}"
