"""
TCBS provider plugin — ProviderPlugin adapter wrapping vnstock.explorer.tcbs.

All TCBS endpoints require Bearer token authentication. The token must be
provided via the 'token' param or via TCBS_BEARER_TOKEN env var / token file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.providers.tcbs.capabilities import TCBS_CAPABILITIES, TCBS_LIMITATIONS
from vnstock.providers.tcbs.normalize import normalize_equity_ohlcv

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

_SUPPORTED_DATASETS = frozenset(
    d for d, cap in TCBS_CAPABILITIES.items() if cap.get("supported")
)


class TCBSProviderPlugin:
    """ProviderPlugin adapter for TCBS market data provider."""

    name: str = "TCBS"

    def capabilities(self) -> dict[str, Any]:
        return TCBS_CAPABILITIES

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        if not params.get("symbol"):
            raise ValueError(f"'symbol' is required for dataset '{dataset}'.")

    def fetch(self, dataset: str, params: dict[str, Any]) -> pd.DataFrame:
        if dataset not in _SUPPORTED_DATASETS:
            raise UnsupportedDatasetForProviderError(self.name, dataset)
        handler = self._dataset_handlers.get(dataset)
        if handler is None:
            raise UnsupportedDatasetForProviderError(self.name, dataset)
        try:
            return handler(params)
        except (UnsupportedDatasetForProviderError, ProviderFetchError):
            raise
        except Exception as exc:
            raise ProviderFetchError(self.name, dataset, cause=exc) from exc

    def diagnostics(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": "ok",
            "supported_datasets": sorted(_SUPPORTED_DATASETS),
            "limitations": TCBS_LIMITATIONS,
        }

    def auth_spec(self, dataset: str) -> "AuthSpec":
        """TCBS requires interactive login; experimental and explicit-only.

        TCBS authenticated mode is experimental and only used when the caller
        explicitly selects ``source="TCBS"`` with an auth policy that allows it.
        """
        from vnstock.core.auth.spec import AuthSpec

        return AuthSpec.tcbs_experimental(
            scopes=(
                "equity.ohlcv",
                "equity.quote",
                "equity.intraday_trades",
                "reference.company_info",
                "fundamental.balance_sheet",
                "fundamental.income_statement",
                "fundamental.cash_flow",
                "fundamental.financial_ratio",
            )
        )

    @property
    def _dataset_handlers(self) -> dict[str, Any]:
        return {
            "equity.ohlcv": self._fetch_equity_ohlcv,
            "equity.quote": self._fetch_equity_quote,
            "equity.intraday_trades": self._fetch_intraday_trades,
            "reference.company_info": self._fetch_company_info,
            "fundamental.balance_sheet": self._fetch_balance_sheet,
            "fundamental.income_statement": self._fetch_income_statement,
            "fundamental.cash_flow": self._fetch_cash_flow,
            "fundamental.financial_ratio": self._fetch_financial_ratio,
        }

    def _fetch_equity_ohlcv(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.tcbs.quote import Quote

        symbol = params["symbol"]
        q = Quote(
            symbol=symbol,
            token=params.get("token"),
            show_log=params.get("show_log", False),
        )
        df = q.history(
            start=params.get("start"),
            end=params.get("end"),
            interval=params.get("interval", "1D"),
            count_back=params.get("count_back"),
            show_log=params.get("show_log", False),
        )
        df = normalize_equity_ohlcv(df, symbol)
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.ohlcv")
        return df

    def _fetch_equity_quote(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.tcbs.trading import Trading

        symbols = params.get("symbols_list", params.get("symbol", []))
        if isinstance(symbols, str):
            symbols = [symbols]
        t = Trading(token=params.get("token"), show_log=params.get("show_log", False))
        df = t.price_board(symbols_list=symbols, show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.quote")
        return df

    def _fetch_intraday_trades(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.tcbs.quote import Quote

        symbol = params["symbol"]
        q = Quote(
            symbol=symbol,
            token=params.get("token"),
            show_log=params.get("show_log", False),
        )
        df = q.intraday(
            page=params.get("page", 0),
            size=params.get("size", 100),
            show_log=params.get("show_log", False),
        )
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.intraday_trades")
        return df

    def _fetch_company_info(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.tcbs.company import Company

        symbol = params["symbol"]
        c = Company(
            symbol=symbol,
            token=params.get("token"),
            show_log=params.get("show_log", False),
        )
        df = c.overview(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "reference.company_info")
        return df

    def _fetch_balance_sheet(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.tcbs.financial import Finance

        symbol = params["symbol"]
        f = Finance(
            symbol=symbol,
            token=params.get("token"),
            show_log=params.get("show_log", False),
        )
        df = f.balance_sheet(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fundamental.balance_sheet")
        return df

    def _fetch_income_statement(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.tcbs.financial import Finance

        symbol = params["symbol"]
        f = Finance(
            symbol=symbol,
            token=params.get("token"),
            show_log=params.get("show_log", False),
        )
        df = f.income_statement(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fundamental.income_statement")
        return df

    def _fetch_cash_flow(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.tcbs.financial import Finance

        symbol = params["symbol"]
        f = Finance(
            symbol=symbol,
            token=params.get("token"),
            show_log=params.get("show_log", False),
        )
        df = f.cash_flow(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fundamental.cash_flow")
        return df

    def _fetch_financial_ratio(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.tcbs.financial import Finance

        symbol = params["symbol"]
        f = Finance(
            symbol=symbol,
            token=params.get("token"),
            show_log=params.get("show_log", False),
        )
        df = f.ratio(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fundamental.financial_ratio")
        return df
