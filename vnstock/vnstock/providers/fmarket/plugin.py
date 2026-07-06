"""
FMarket provider plugin — ProviderPlugin adapter wrapping vnstock.explorer.fmarket.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.providers.fmarket.capabilities import (
    FMARKET_CAPABILITIES,
    FMARKET_LIMITATIONS,
)

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

_SUPPORTED_DATASETS = frozenset(
    d for d, cap in FMARKET_CAPABILITIES.items() if cap.get("supported")
)


class FMarketProviderPlugin:
    """ProviderPlugin adapter for FMarket fund data provider."""

    name: str = "FMARKET"

    def capabilities(self) -> dict[str, Any]:
        return FMARKET_CAPABILITIES

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        if dataset == "fund.nav" and not params.get("symbol"):
            raise ValueError("'symbol' (fund short_name) is required for fund.nav.")

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
            "limitations": FMARKET_LIMITATIONS,
        }

    def auth_spec(self, dataset: str) -> "AuthSpec":
        """FMarket is a public provider — no authentication required."""
        from vnstock.core.auth.spec import AuthSpec

        return AuthSpec.no_auth()

    @property
    def _dataset_handlers(self) -> dict[str, Any]:
        return {
            "fund.nav": self._fetch_fund_nav,
            "reference.symbols": self._fetch_reference_symbols,
        }

    def _fetch_fund_nav(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.fmarket.fund import Fund

        symbol = params["symbol"]
        f = Fund(symbol=symbol, show_log=params.get("show_log", False))
        df = f.nav_report(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "fund.nav")
        return df

    def _fetch_reference_symbols(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.fmarket.fund import Fund

        f = Fund(show_log=params.get("show_log", False))
        df = f.listing(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "reference.symbols")
        return df
