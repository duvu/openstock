from typing import Any, Optional

from vnai import optimize_execution

from vnstock.ui._base import BaseDetailUI


class EquityMarket(BaseDetailUI):
    """Equity market data.

    These datasets are migrated to the canonical plugin-runtime contract.
    Every request is served through :meth:`BaseDetailUI._plugin_dispatch`
    (the fail-closed :class:`PluginRuntime` boundary) and never silently
    drops into legacy explorer dispatch. A provider that cannot serve the
    request returns a typed failure to the caller.
    """

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
        """Get historical OHLCV data via the canonical ``equity.ohlcv`` dataset."""
        # Handle parameter aliases
        interval = kwargs.pop("resolution", interval)
        count_back = kwargs.pop("length", count)

        params = {
            "symbol": self.symbol,
            "start": start,
            "end": end,
            "interval": interval,
            "count_back": count_back,
            **{k: v for k, v in kwargs.items() if k not in ("source",)},
        }
        return self._plugin_dispatch(
            "equity.ohlcv",
            params,
            source=source,
        )

    @optimize_execution("UI")
    def trades(self, source: str = "kbs", **kwargs) -> Any:
        """Get intraday trades via the canonical ``equity.intraday_trades`` dataset."""
        kwargs.pop("interval", None)

        params = {
            "symbol": self.symbol,
            **{k: v for k, v in kwargs.items() if k not in ("source",)},
        }
        return self._plugin_dispatch(
            "equity.intraday_trades",
            params,
            source=source,
        )

    @optimize_execution("UI")
    def quote(self, source: str = "kbs", **kwargs) -> Any:
        """Get real-time quote snapshot via the canonical ``equity.quote`` dataset."""
        params = {
            "symbol": self.symbol,
            **{k: v for k, v in kwargs.items() if k not in ("source",)},
        }
        return self._plugin_dispatch(
            "equity.quote",
            params,
            source=source,
        )
