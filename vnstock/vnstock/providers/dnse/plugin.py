"""
DNSE provider plugin — ProviderPlugin adapter wrapping vnstock.explorer.dnse.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.providers.dnse.capabilities import DNSE_CAPABILITIES, DNSE_LIMITATIONS
from vnstock.providers.dnse.normalize import normalize_equity_ohlcv

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

_SUPPORTED_DATASETS = frozenset(
    d for d, cap in DNSE_CAPABILITIES.items() if cap.get("supported")
)


class DNSEProviderPlugin:
    """ProviderPlugin adapter for DNSE market data provider."""

    name: str = "DNSE"

    def capabilities(self) -> dict[str, Any]:
        return DNSE_CAPABILITIES

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
            "limitations": DNSE_LIMITATIONS,
        }

    def auth_spec(self, dataset: str) -> "AuthSpec":
        """DNSE is a public provider — no authentication required."""
        from vnstock.core.auth.spec import AuthSpec

        return AuthSpec.no_auth()

    @property
    def _dataset_handlers(self) -> dict[str, Any]:
        return {
            "equity.ohlcv": self._fetch_equity_ohlcv,
            "equity.quote": self._fetch_equity_quote,
        }

    def _fetch_equity_ohlcv(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.dnse.quote import Quote

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
        from vnstock.explorer.dnse.trading import Trading

        symbols = params.get("symbols_list", params.get("symbol", []))
        if isinstance(symbols, str):
            symbols = [symbols]
        t = Trading(show_log=params.get("show_log", False))
        df = t.price_board(symbols_list=symbols, show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.quote")
        return df
