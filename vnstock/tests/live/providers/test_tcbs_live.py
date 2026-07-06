"""
Live smoke tests for TCBS provider.

These tests call real TCBS endpoints and require network access.
They are disabled by default. Enable with:

    VNSTOCK_LIVE_TESTS=true pytest tests/live/providers/test_tcbs_live.py -m live

Optional filtering:

    VNSTOCK_LIVE_SYMBOLS=FPT  # test a single symbol

Note: TCBS uses unofficial public endpoints — availability may vary.
"""

import pytest

from tests.live.conftest import LIVE_SYMBOLS, skip_if_provider_excluded

pytestmark = [pytest.mark.live, pytest.mark.provider, pytest.mark.provider_tcbs]

_PROVIDER = "TCBS"

# Use only the first symbol to stay rate-limit friendly
_SYMBOL = LIVE_SYMBOLS[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_quote(symbol: str):
    from vnstock.explorer.tcbs.quote import Quote

    return Quote(symbol=symbol)


def _get_trading():
    from vnstock.explorer.tcbs.trading import Trading

    return Trading()


def _get_company(symbol: str):
    from vnstock.explorer.tcbs.company import Company

    return Company(symbol=symbol)


def _get_finance(symbol: str):
    from vnstock.explorer.tcbs.financial import Finance

    return Finance(symbol=symbol, period="quarter")


# ---------------------------------------------------------------------------
# OHLCV live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestTCBSLiveOHLCV:
    """Verify TCBS OHLCV endpoint returns parseable, schema-valid data."""

    def test_history_returns_dataframe(self):
        """TCBS history() returns a non-empty DataFrame."""
        import pandas as pd

        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty, "DataFrame should not be empty"

    def test_history_has_ohlcv_columns(self):
        """TCBS history() output has required OHLCV columns."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        for col in ("time", "open", "high", "low", "close", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_history_numeric_prices(self):
        """TCBS OHLCV prices are positive finite numbers."""
        import numpy as np

        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        for col in ("open", "high", "low", "close"):
            assert (df[col] > 0).all(), f"Non-positive price in column {col}"
            assert np.isfinite(df[col]).all(), f"Non-finite price in column {col}"

    def test_history_time_is_datetime(self):
        """TCBS history time column is datetime type."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        assert df["time"].dtype.name.startswith("datetime"), (
            f"time dtype should be datetime, got {df['time'].dtype}"
        )

    def test_history_no_raw_array_keys(self):
        """Normalized TCBS output does not expose raw array field names like 't', 'o'."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        raw_keys = {"t", "o", "h", "l", "c", "v"}
        leaked = raw_keys & set(df.columns)
        assert not leaked, f"Raw keys leaked into normalized output: {leaked}"

    def test_history_endpoint_variant_in_attrs(self):
        """TCBS history attrs should record which endpoint was used."""
        q = _get_quote(_SYMBOL)
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        assert "endpoint_variant" in df.attrs
        assert "tcbs.com.vn" in df.attrs["endpoint_variant"]

    def test_history_fallback_endpoint_on_symbol_variant(self):
        """Use different symbol to test TCBS endpoint resilience."""
        q = _get_quote("VCB")
        df = q.history(start="2026-06-01", end="2026-06-30", interval="1D")

        assert not df.empty


# ---------------------------------------------------------------------------
# Price board live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestTCBSLivePriceBoard:
    """Verify TCBS price_board endpoint returns parseable, schema-valid data."""

    def test_price_board_returns_dataframe(self):
        """TCBS price_board() returns a non-empty DataFrame."""
        import pandas as pd

        t = _get_trading()
        df = t.price_board(symbols_list=[_SYMBOL])

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty, "DataFrame should not be empty"

    def test_price_board_has_required_columns(self):
        """TCBS price_board() output contains minimum required columns."""
        t = _get_trading()
        df = t.price_board(symbols_list=[_SYMBOL])

        for col in ("symbol", "close_price", "volume_accumulated"):
            assert col in df.columns, f"Missing price board column: {col}"

    def test_price_board_multi_symbol(self):
        """TCBS price_board() handles multiple symbols."""
        t = _get_trading()
        df = t.price_board(symbols_list=["FPT", "VCB"])

        assert len(df) >= 1  # May not have all symbols in response

    def test_price_board_metadata_set(self):
        """TCBS price_board() sets attrs correctly."""
        t = _get_trading()
        df = t.price_board(symbols_list=[_SYMBOL])

        assert df.attrs.get("source") == "TCBS"


# ---------------------------------------------------------------------------
# Intraday live smoke test (experimental)
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestTCBSLiveIntraday:
    """Verify TCBS intraday endpoint returns parseable data (experimental)."""

    def test_intraday_returns_dataframe(self):
        """TCBS intraday() returns a DataFrame (may be empty on non-trading day)."""
        import pandas as pd

        q = _get_quote(_SYMBOL)
        df = q.intraday()

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"

    def test_intraday_has_expected_columns_when_nonempty(self):
        """TCBS intraday() has required columns if data is present."""
        q = _get_quote(_SYMBOL)
        df = q.intraday()

        if df.empty:
            pytest.skip("No intraday data (non-trading day or after hours)")

        for col in ("time", "price", "volume"):
            assert col in df.columns, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# Company live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestTCBSLiveCompany:
    """Verify TCBS Company endpoints return parseable, schema-valid data."""

    def test_overview_returns_dataframe(self):
        """TCBS company overview() returns a non-empty DataFrame."""
        import pandas as pd

        c = _get_company(_SYMBOL)
        df = c.overview()

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty

    def test_overview_has_required_columns(self):
        """TCBS overview() has standard company columns."""
        c = _get_company(_SYMBOL)
        df = c.overview()

        for col in ("symbol", "exchange", "industry"):
            assert col in df.columns, f"Missing column: {col}"

    def test_overview_symbol_matches(self):
        """TCBS overview symbol matches the requested symbol."""
        c = _get_company(_SYMBOL)
        df = c.overview()

        assert df.iloc[0]["symbol"] == _SYMBOL

    def test_shareholders_returns_dataframe(self):
        import pandas as pd

        c = _get_company(_SYMBOL)
        df = c.shareholders()

        assert isinstance(df, pd.DataFrame)

    def test_officers_returns_dataframe(self):
        import pandas as pd

        c = _get_company(_SYMBOL)
        df = c.officers()

        assert isinstance(df, pd.DataFrame)

    def test_dividends_returns_dataframe(self):
        import pandas as pd

        c = _get_company(_SYMBOL)
        df = c.dividends()

        assert isinstance(df, pd.DataFrame)


# ---------------------------------------------------------------------------
# Finance live smoke test
# ---------------------------------------------------------------------------


@skip_if_provider_excluded(_PROVIDER)
class TestTCBSLiveFinance:
    """Verify TCBS Finance endpoints return parseable, schema-valid data."""

    def test_balance_sheet_returns_dataframe(self):
        import pandas as pd

        f = _get_finance(_SYMBOL)
        df = f.balance_sheet()

        assert isinstance(df, pd.DataFrame), "Expected DataFrame"
        assert not df.empty

    def test_balance_sheet_has_metadata_columns(self):
        f = _get_finance(_SYMBOL)
        df = f.balance_sheet()

        for col in ("symbol", "period_type", "provider"):
            assert col in df.columns, f"Missing metadata column: {col}"

    def test_income_statement_returns_dataframe(self):
        import pandas as pd

        f = _get_finance(_SYMBOL)
        df = f.income_statement()

        assert isinstance(df, pd.DataFrame)

    def test_cash_flow_returns_dataframe(self):
        import pandas as pd

        f = _get_finance(_SYMBOL)
        df = f.cash_flow()

        assert isinstance(df, pd.DataFrame)

    def test_ratio_returns_dataframe(self):
        import pandas as pd

        f = _get_finance(_SYMBOL)
        df = f.ratio()

        assert isinstance(df, pd.DataFrame)
