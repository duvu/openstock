from typing import Any, Optional

from vnai import optimize_execution

from vnstock.ui._base import BaseDetailUI


class EquityMarket(BaseDetailUI):
    """Equity market data."""

    @optimize_execution("UI")
    def ohlcv(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1D",
        count: int = 100,
        source: str = "kbs",
        **kwargs,
    ) -> Any:
        """Get historical OHLCV data."""
        # Handle parameter aliases
        interval = kwargs.pop("resolution", interval)
        count_back = kwargs.pop("length", count)

        # Try PluginRuntime path first; fall back to legacy if PluginRuntime
        # cannot serve this request (e.g., provider not yet migrated).
        params = {
            "symbol": self.symbol,
            "start": start,
            "end": end,
            "interval": interval,
            "count_back": count_back,
            **{k: v for k, v in kwargs.items() if k not in ("source",)},
        }
        result = self._plugin_dispatch(
            "equity.ohlcv",
            params,
            source=source,
            allow_legacy_fallback=True,
        )
        if result is not None:
            return result
        # Legacy fallback
        return self._dispatch(
            "equity_market",
            "ohlcv",
            start=start,
            end=end,
            interval=interval,
            count_back=count_back,
            source=source,
            **kwargs,
        )

    @optimize_execution("UI")
    def trades(self, source: str = "kbs", **kwargs) -> Any:
        """Get intraday trades."""
        kwargs.pop("interval", None)

        params = {
            "symbol": self.symbol,
            **{k: v for k, v in kwargs.items() if k not in ("source",)},
        }
        result = self._plugin_dispatch(
            "equity.intraday_trades",
            params,
            source=source,
            allow_legacy_fallback=True,
        )
        if result is not None:
            return result
        return self._dispatch("equity_market", "trades", source=source, **kwargs)

    @optimize_execution("UI")
    def quote(self, source: str = "kbs", **kwargs) -> Any:
        """Get real-time quote snapshot."""
        params = {
            "symbol": self.symbol,
            **{k: v for k, v in kwargs.items() if k not in ("source",)},
        }
        result = self._plugin_dispatch(
            "equity.quote",
            params,
            source=source,
            allow_legacy_fallback=True,
        )
        if result is not None:
            return result
        return self._dispatch("equity_market", "quote", source=source, **kwargs)
