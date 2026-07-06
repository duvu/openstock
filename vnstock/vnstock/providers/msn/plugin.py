"""
MSN provider plugin — ProviderPlugin adapter wrapping vnstock.explorer.msn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.providers.msn.capabilities import MSN_CAPABILITIES, MSN_LIMITATIONS
from vnstock.providers.msn.normalize import normalize_equity_ohlcv

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

_SUPPORTED_DATASETS = frozenset(
    d for d, cap in MSN_CAPABILITIES.items() if cap.get("supported")
)


class MSNProviderPlugin:
    """ProviderPlugin adapter for MSN market data provider."""

    name: str = "MSN"

    def capabilities(self) -> dict[str, Any]:
        return MSN_CAPABILITIES

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        # MSN requires symbol_id (not just ticker symbol)
        if not params.get("symbol") and not params.get("symbol_id"):
            raise ValueError(
                "'symbol' or 'symbol_id' is required for MSN OHLCV. "
                "Use Listing.search_symbol() to resolve symbol_id first."
            )

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
            "limitations": MSN_LIMITATIONS,
        }

    def auth_spec(self, dataset: str) -> "AuthSpec":
        """MSN is a public provider — no authentication required."""
        from vnstock.core.auth.spec import AuthSpec

        return AuthSpec.no_auth()

    @property
    def _dataset_handlers(self) -> dict[str, Any]:
        return {
            "equity.ohlcv": self._fetch_equity_ohlcv,
        }

    def _fetch_equity_ohlcv(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.explorer.msn.quote import Quote

        # MSN uses symbol_id, not ticker symbol
        symbol_id = params.get("symbol_id") or params.get("symbol")
        symbol = params.get("symbol", symbol_id)
        q = Quote(symbol=symbol_id, show_log=params.get("show_log", False))
        df = q.history(
            start=params.get("start"),
            end=params.get("end"),
            interval=params.get("interval", "1D"),
            show_log=params.get("show_log", False),
        )
        df = normalize_equity_ohlcv(df, symbol)
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.ohlcv")
        return df
