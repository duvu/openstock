"""
FMP provider plugin — ProviderPlugin adapter wrapping vnstock.connector.fmp.

Requires FMP_API_KEY environment variable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.providers.fmp.capabilities import FMP_CAPABILITIES, FMP_LIMITATIONS
from vnstock.providers.fmp.normalize import normalize_equity_ohlcv

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

_SUPPORTED_DATASETS = frozenset(
    d for d, cap in FMP_CAPABILITIES.items() if cap.get("supported")
)


class FMPProviderPlugin:
    """ProviderPlugin adapter for FMP market data provider."""

    name: str = "FMP"

    def capabilities(self) -> dict[str, Any]:
        return FMP_CAPABILITIES

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
            "limitations": FMP_LIMITATIONS,
        }

    def auth_spec(self, dataset: str) -> "AuthSpec":
        """FMP requires an API key but uses a static env-based credential.

        FMP is not interactive-login based; the API key is configured via
        environment variable ``FMP_API_KEY``. We declare it as API_KEY type
        but not experimental.
        """
        from vnstock.core.auth.spec import AuthSpec
        from vnstock.core.auth.types import AuthType

        return AuthSpec(
            auth_type=AuthType.API_KEY,
            required=True,
            experimental=False,
            explicit_only=False,
            notes="FMP API key required. Set via FMP_API_KEY env var.",
        )

    @property
    def _dataset_handlers(self) -> dict[str, Any]:
        return {
            "equity.ohlcv": self._fetch_equity_ohlcv,
            "equity.quote": self._fetch_equity_quote,
            "fundamental.balance_sheet": self._fetch_balance_sheet,
            "fundamental.income_statement": self._fetch_income_statement,
            "fundamental.cash_flow": self._fetch_cash_flow,
        }

    def _fetch_equity_ohlcv(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.connector.fmp.quote import Quote

        symbol = params["symbol"]
        q = Quote(symbol=symbol, show_log=params.get("show_log", False))
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

    def _fetch_equity_quote(self, params: dict[str, Any]) -> pd.DataFrame:
        from vnstock.connector.fmp.quote import Quote

        symbol = params["symbol"]
        q = Quote(symbol=symbol, show_log=params.get("show_log", False))
        df = q.short(show_log=params.get("show_log", False))
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", "equity.quote")
        return df

    def _fetch_balance_sheet(self, params: dict[str, Any]) -> pd.DataFrame:
        raise UnsupportedDatasetForProviderError(
            self.name,
            "fundamental.balance_sheet",
        )

    def _fetch_income_statement(self, params: dict[str, Any]) -> pd.DataFrame:
        raise UnsupportedDatasetForProviderError(
            self.name,
            "fundamental.income_statement",
        )

    def _fetch_cash_flow(self, params: dict[str, Any]) -> pd.DataFrame:
        raise UnsupportedDatasetForProviderError(
            self.name,
            "fundamental.cash_flow",
        )
