"""
Live smoke tests for KBS provider.

These tests call real KBS endpoints and require network access.
They are disabled by default. Enable with:

    VNSTOCK_LIVE_TESTS=true pytest tests/live/providers/test_kbs_live.py -m live

Optional filtering:

    VNSTOCK_LIVE_SYMBOLS=FPT  # test a single symbol
"""

import pytest

from tests.live.conftest import LIVE_SYMBOLS, skip_if_provider_excluded

pytestmark = [pytest.mark.live, pytest.mark.provider, pytest.mark.provider_kbs]

_PROVIDER = "KBS"

# Use only the first symbol to stay rate-limit friendly
_SYMBOL = LIVE_SYMBOLS[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_quote(symbol: str):
    from vnstock.explorer.kbs.quote import Quote

    return Quote(symbol=symbol)


def _get_trading(symbol: str):
    from vnstock.explorer.kbs.trading import Trading

    return Trading(symbol=symbol)


# ---------------------------------------------------------------------------
# OHLCV live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestKBSLiveOHLCV:
    """Verify KBS OHLCV endpoint returns parseable, schema-valid data."""

    def test_history_returns_dataframe(self):
        """KBS history() returns a non-empty DataFrame."""
        import pandas as pd

        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty, "DataFrame should not be empty"

    def test_history_has_ohlcv_columns(self):
        """KBS history() output has required OHLCV columns."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        for col in ("time", "open", "high", "low", "close", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_history_numeric_prices(self):
        """KBS OHLCV prices are positive finite numbers."""
        import numpy as np

        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        for col in ("open", "high", "low", "close"):
            assert (df[col] > 0).all(), f"Non-positive price in column {col}"
            assert np.isfinite(df[col]).all(), f"Non-finite price in column {col}"

    def test_history_no_raw_milli_vnd_keys(self):
        """Normalized KBS output does not expose raw milli-VND field names."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        # KBS raw format uses {"data_day": [{"t": "YYYY-MM-DD", "o": ...}]}
        raw_keys = {"t", "o", "h", "l", "c", "v"}
        leaked = raw_keys & set(df.columns)
        assert not leaked, f"Raw keys leaked into normalized output: {leaked}"

    def test_history_prices_not_in_milli_vnd(self):
        """KBS prices should be in VND, not milli-VND (divided by 1000)."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        # Typical VN stock price range: 1,000 – 500,000 VND
        # Milli-VND would be 1,000,000 – 500,000,000 (suspiciously large)
        assert (df["close"] < 2_000_000).all(), (
            "Close prices look like milli-VND; normalization (/1000) may have failed"
        )


# ---------------------------------------------------------------------------
# Price board live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestKBSLivePriceBoard:
    """Verify KBS price_board endpoint returns parseable, schema-valid data."""

    def test_price_board_returns_dataframe(self):
        """KBS price_board() returns a non-empty DataFrame."""
        import pandas as pd

        t = _get_trading(_SYMBOL)
        df = t.price_board(symbols_list=[_SYMBOL])

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty, "DataFrame should not be empty"

    def test_price_board_no_raw_kbs_codes(self):
        """KBS price_board() normalized output does not expose raw KBS field codes."""
        t = _get_trading(_SYMBOL)
        df = t.price_board(symbols_list=[_SYMBOL])

        # KBS raw codes that should not appear in normalized output
        raw_codes = {"SB", "CP", "CL", "FL", "RE", "TT"}
        leaked = raw_codes & set(df.columns)
        assert not leaked, (
            f"Raw KBS field codes leaked into normalized output: {leaked}"
        )

    def test_price_board_rate_limit_friendly(self):
        """KBS price_board() can be called with a minimal symbol set."""
        t = _get_trading(_SYMBOL)
        df = t.price_board(symbols_list=[_SYMBOL])
        assert df is not None
