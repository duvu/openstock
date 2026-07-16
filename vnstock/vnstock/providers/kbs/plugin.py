"""
KBS provider plugin — ProviderPlugin adapter wrapping vnstock.explorer.kbs.

This is the primary/default Vietnamese market data provider.
Existing public API (Market().equity.ohlcv(...)) continues to route through
the legacy explorer path; this plugin enables routing through the Phase 1
PluginRegistry/PluginRouter when explicitly requested.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.corporate_actions import normalize_corporate_actions
from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.providers.kbs.capabilities import KBS_CAPABILITIES, KBS_LIMITATIONS
from vnstock.providers.kbs.normalize import (
    normalize_equity_ohlcv,
    normalize_equity_quote,
)

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

_SUPPORTED_DATASETS = frozenset(
    d for d, cap in KBS_CAPABILITIES.items() if cap.get("supported")
)


class KBSProviderPlugin:
    """ProviderPlugin adapter for KBS market data provider."""

    name: str = "KBS"

    def capabilities(self) -> dict[str, Any]:
        return KBS_CAPABILITIES

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        if not params.get("symbol") and dataset not in (
            "equity.quote",
            "reference.symbols",
        ):
            raise ValueError(f"'symbol' is required for dataset '{dataset}'.")
        if dataset == "reference.corporate_actions":
            for key in ("start", "end"):
                value = params.get(key)
                if value:
                    try:
                        pd.Timestamp(value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"'{key}' must be an ISO date.") from exc
            if (
                params.get("start")
                and params.get("end")
                and pd.Timestamp(params["start"]) > pd.Timestamp(params["end"])
            ):
                raise ValueError("'start' must not be after 'end'.")
            page = params.get("page", 1)
            page_size = params.get("page_size", 500)
            if isinstance(page, bool) or not isinstance(page, int) or page < 1:
                raise ValueError("'page' must be a positive integer.")
            if (
                isinstance(page_size, bool)
                or not isinstance(page_size, int)
                or not 1 <= page_size <= 500
            ):
                raise ValueError("'page_size' must be between 1 and 500.")

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
            "limitations": KBS_LIMITATIONS,
        }

    def auth_spec(self, dataset: str) -> "AuthSpec":
        """KBS is a public provider — no authentication required."""
        from vnstock.core.auth.spec import AuthSpec

        return AuthSpec.no_auth()

    # ------------------------------------------------------------------
    # Dataset handlers
    # ------------------------------------------------------------------

    @property
    def _dataset_handlers(self) -> dict[str, Any]:
        return {
            "equity.ohlcv": self._fetch_equity_ohlcv,
            "equity.quote": self._fetch_equity_quote,
            "equity.intraday_trades": self._fetch_intraday_trades,
            "index.ohlcv": self._fetch_index_ohlcv,
            "reference.symbols": self._fetch_reference_symbols,
            "reference.company_info": self._fetch_company_info,
            "reference.corporate_actions": self._fetch_corporate_actions,
            "fundamental.balance_sheet": self._fetch_balance_sheet,
            "fundamental.income_statement": self._fetch_income_statement,
            "fundamental.cash_flow": self._fetch_cash_flow,
            "fundamental.financial_ratio": self._fetch_financial_ratio,
        }

    def _fetch_equity_ohlcv(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.quote import Quote

        symbol = params["symbol"]
        q = Quote(symbol=symbol, show_log=params.get("show_log", False))
        df = q.history(
            start=params.get("start"),
            end=params.get("end"),
            interval=params.get("interval", "1D"),
            count_back=params.get("count_back"),
            floating=params.get("floating", 2),
            get_all=params.get("get_all", False),
            show_log=params.get("show_log", False),
        )
        df = normalize_equity_ohlcv(df, symbol)
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.ohlcv")
        return df

    def _fetch_equity_quote(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.trading import Trading

        symbols = params.get("symbols_list", params.get("symbol", []))
        if isinstance(symbols, str):
            symbols = [symbols]
        t = Trading(show_log=params.get("show_log", False))
        df = t.price_board(symbols_list=symbols, show_log=params.get("show_log", False))
        df = normalize_equity_quote(df)
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.quote")
        return df

    def _fetch_intraday_trades(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.trading import Trading

        symbol = params["symbol"]
        t = Trading(symbol=symbol, show_log=params.get("show_log", False))
        df = t.intraday(
            page=params.get("page", 0),
            size=params.get("size", 100),
            show_log=params.get("show_log", False),
        )
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.intraday_trades")
        return df

    def _fetch_index_ohlcv(self, params: dict[str, Any]) -> pd.DataFrame:
        return self._fetch_equity_ohlcv(params)

    def _fetch_reference_symbols(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.listing import Listing

        lst = Listing(show_log=params.get("show_log", False))
        df = lst.all_symbols(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "reference.symbols")
        return df

    def _fetch_corporate_actions(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.company import Company

        symbol = str(params["symbol"]).strip().upper()
        company = Company(symbol=symbol, show_log=params.get("show_log", False))
        frame = company.events(
            event_type=params.get("event_type"),
            page=int(params.get("page", 1)),
            page_size=int(params.get("page_size", 500)),
            show_log=params.get("show_log", False),
        )
        return normalize_corporate_actions(
            frame,
            provider="KBS",
            symbol=symbol,
            start=params.get("start"),
            end=params.get("end"),
        )

    def _fetch_company_info(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.company import Company

        symbol = params["symbol"]
        c = Company(symbol=symbol, show_log=params.get("show_log", False))
        df = c.overview(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "reference.company_info")
        return df

    def _fetch_balance_sheet(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.financial import Finance

        symbol = params["symbol"]
        f = Finance(symbol=symbol, show_log=params.get("show_log", False))
        df = f.balance_sheet(
            period=params.get("period", "year"),
            lang=params.get("lang", "vi"),
            show_log=params.get("show_log", False),
        )
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fundamental.balance_sheet")
        return df

    def _fetch_income_statement(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.financial import Finance

        symbol = params["symbol"]
        f = Finance(symbol=symbol, show_log=params.get("show_log", False))
        df = f.income_statement(
            period=params.get("period", "year"),
            lang=params.get("lang", "vi"),
            show_log=params.get("show_log", False),
        )
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fundamental.income_statement")
        return df

    def _fetch_cash_flow(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.financial import Finance

        symbol = params["symbol"]
        f = Finance(symbol=symbol, show_log=params.get("show_log", False))
        df = f.cash_flow(
            period=params.get("period", "year"),
            lang=params.get("lang", "vi"),
            show_log=params.get("show_log", False),
        )
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fundamental.cash_flow")
        return df

    def _fetch_financial_ratio(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.kbs.financial import Finance

        symbol = params["symbol"]
        f = Finance(symbol=symbol, show_log=params.get("show_log", False))
        df = f.ratio(
            period=params.get("period", "year"),
            lang=params.get("lang", "vi"),
            show_log=params.get("show_log", False),
        )
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fundamental.financial_ratio")
        return df
