"""
KBS OHLCV provider plugin for the vnstock plugin architecture.

This module wraps the existing KBS Quote explorer to conform to the
ProviderPlugin protocol, allowing it to be used through the new
PluginRegistry / PluginRouter path.

This is the Phase 1 first provider path adaptation (tasks 69-76).
The existing KBS Quote class is unchanged; this is a thin adapter layer.

Usage (internal)::

    from vnstock.core.provider.plugins.kbs_ohlcv import KBSOHLCVPlugin

    plugin = KBSOHLCVPlugin()
    df = plugin.fetch("equity.ohlcv", {"symbol": "FPT", "start": "2024-01-01"})
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.explorer.kbs.quote import Quote  # noqa: E402

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

#: Datasets this plugin supports.
_SUPPORTED_DATASETS = frozenset({"equity.ohlcv", "index.ohlcv"})


class KBSOHLCVPlugin:
    """ProviderPlugin adapter for KBS OHLCV equity data.

    Wraps ``vnstock.explorer.kbs.quote.Quote`` to conform to the
    :class:`~vnstock.core.provider.plugin.ProviderPlugin` protocol.
    """

    name: str = "KBS"

    def capabilities(self) -> dict[str, Any]:
        """Return KBS OHLCV capability metadata."""
        return {
            "equity.ohlcv": {
                "supported": True,
                "status": "stable",
                "auth_required": False,
                "intervals": ["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
                "notes": "Default daily OHLCV provider for Vietnamese equities.",
            },
            "index.ohlcv": {
                "supported": True,
                "status": "stable",
                "auth_required": False,
                "intervals": ["1D", "1W", "1M"],
                "notes": "OHLCV bars for Vietnamese market indices.",
            },
        }

    def fetch(self, dataset: str, params: dict[str, Any]) -> pd.DataFrame:
        """Fetch OHLCV data from KBS.

        Args:
            dataset: Must be ``"equity.ohlcv"`` or ``"index.ohlcv"``.
            params: Keys used:
                - ``symbol`` (required)
                - ``start`` (optional, default None)
                - ``end`` (optional, default None)
                - ``interval`` (optional, default ``"1D"``)
                - ``count_back`` (optional)
                - ``floating`` (optional, default 2)

        Returns:
            DataFrame with columns: time, open, high, low, close, volume,
            plus df.attrs metadata.

        Raises:
            UnsupportedDatasetForProviderError: If dataset is not supported.
            ProviderFetchError: On fetch failure.
        """
        if dataset not in _SUPPORTED_DATASETS:
            raise UnsupportedDatasetForProviderError(self.name, dataset)

        symbol: str = params.get("symbol", "")
        if not symbol:
            raise ValueError("KBSOHLCVPlugin.fetch requires 'symbol' in params.")

        try:
            q = Quote(
                symbol=symbol,
                show_log=params.get("show_log", False),
                random_agent=params.get("random_agent", False),
                proxy_config=params.get("proxy_config"),
                proxy_mode=params.get("proxy_mode"),
                proxy_list=params.get("proxy_list"),
            )
            df: pd.DataFrame = q.history(
                start=params.get("start"),
                end=params.get("end"),
                interval=params.get("interval", "1D"),
                count_back=params.get("count_back"),
                floating=params.get("floating", 2),
                get_all=params.get("get_all", False),
                show_log=params.get("show_log", False),
            )
        except Exception as exc:
            raise ProviderFetchError(self.name, dataset, cause=exc) from exc

        # Attach plugin metadata
        df.attrs.setdefault("provider", self.name)
        df.attrs.setdefault("dataset", dataset)
        return df

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        """Validate fetch params.

        Args:
            dataset: Dataset name.
            params: Parameters to validate.

        Raises:
            ValueError: If ``symbol`` is missing.
        """
        if not params.get("symbol"):
            raise ValueError(f"'symbol' is required for dataset '{dataset}'.")

    def auth_spec(self, dataset: str) -> "AuthSpec":
        """Return auth spec — KBS is a public provider, no auth needed."""
        from vnstock.core.auth.spec import AuthSpec

        return AuthSpec.no_auth()

    def diagnostics(self) -> dict[str, Any]:
        """Return KBS plugin diagnostics."""
        return {
            "name": self.name,
            "status": "ok",
            "supported_datasets": sorted(_SUPPORTED_DATASETS),
        }
