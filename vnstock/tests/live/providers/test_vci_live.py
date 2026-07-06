"""
Live smoke tests for VCI provider.

These tests call real VCI endpoints and require network access.
They are disabled by default. Enable with:

    VNSTOCK_LIVE_TESTS=true pytest tests/live/providers/test_vci_live.py -m live

Optional filtering:

    VNSTOCK_LIVE_SYMBOLS=FPT  # test a single symbol
"""

import pytest

from tests.live.conftest import LIVE_SYMBOLS, skip_if_provider_excluded

pytestmark = [pytest.mark.live, pytest.mark.provider, pytest.mark.provider_vci]

_PROVIDER = "VCI"

# Use only the first symbol to stay rate-limit friendly
_SYMBOL = LIVE_SYMBOLS[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_quote(symbol: str):
    from vnstock.explorer.vci.quote import Quote

    return Quote(symbol=symbol)


def _get_trading(symbol: str):
    from vnstock.explorer.vci.trading import Trading

    return Trading(symbol=symbol)


# ---------------------------------------------------------------------------
# OHLCV live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestVCILiveOHLCV:
    """Verify VCI OHLCV endpoint returns parseable, schema-valid data."""

    def test_history_returns_dataframe(self):
        """VCI history() returns a non-empty DataFrame."""
        import pandas as pd

        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty, "DataFrame should not be empty"

    def test_history_has_ohlcv_columns(self):
        """VCI history() output has required OHLCV columns."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        for col in ("time", "open", "high", "low", "close", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_history_numeric_prices(self):
        """VCI OHLCV prices are positive finite numbers."""
        import numpy as np

        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        for col in ("open", "high", "low", "close"):
            assert (df[col] > 0).all(), f"Non-positive price in column {col}"
            assert np.isfinite(df[col]).all(), f"Non-finite price in column {col}"

    def test_history_no_raw_vci_array_keys(self):
        """Normalized VCI output does not expose raw VCI array field names."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        # VCI raw format: [{"t": [...], "o": [...], ...}]
        raw_keys = {"t", "o", "h", "l", "c", "v"}
        leaked = raw_keys & set(df.columns)
        assert not leaked, f"Raw keys leaked into normalized output: {leaked}"

    def test_history_rate_limit_friendly(self):
        """VCI history() with a short date range does not trigger rate limit."""
        q = _get_quote(_SYMBOL)
        # Only 5 trading days, minimal data
        df = q.history(start="2026-06-23", end="2026-06-27", interval="1D")
        # May be empty near holidays but should not raise an exception
        assert df is not None


# ---------------------------------------------------------------------------
# Price board live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestVCILivePriceBoard:
    """Verify VCI price_board endpoint returns parseable, schema-valid data."""

    def test_price_board_returns_dataframe(self):
        """VCI price_board() returns a non-empty DataFrame."""
        import pandas as pd

        t = _get_trading(_SYMBOL)
        df = t.price_board(symbols_list=[_SYMBOL])

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty, "DataFrame should not be empty"

    def test_price_board_has_symbol_or_ticker(self):
        """VCI price_board() output contains a symbol/ticker identifier."""
        t = _get_trading(_SYMBOL)
        df = t.price_board(symbols_list=[_SYMBOL])

        symbol_cols = [
            c
            for c in df.columns
            if any(k in c.lower() for k in ("symbol", "ticker", "code"))
        ]
        assert symbol_cols, "No symbol/ticker column found in VCI price_board output"

    def test_price_board_rate_limit_friendly(self):
        """VCI price_board() can be called with a minimal symbol set."""
        t = _get_trading(_SYMBOL)
        df = t.price_board(symbols_list=[_SYMBOL])
        assert df is not None
