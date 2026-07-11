from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from typing import Literal, TypedDict

import duckdb

from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import RunContext

MarketState = Literal[
    "risk_on", "constructive", "mixed", "risk_off", "insufficient_data"
]


class MarketBreadth(TypedDict):
    advancing_symbols: int
    declining_symbols: int
    unchanged_symbols: int


class MarketRegime(TypedDict):
    as_of_date: str
    state: MarketState
    trend: str
    volatility: str
    breadth: MarketBreadth
    methodology: str
    freshness: str
    lineage: dict[str, str]
    quality: str
    caveats: list[str]


class MarketRegimeBuilder:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def build(self, date: str, *, run_ctx: RunContext | None = None) -> MarketRegime:
        benchmark = self._prices("VNINDEX", date)
        breadth = self._breadth(date)
        caveats: list[str] = []
        if len(benchmark) < 2:
            caveats.append("VNINDEX benchmark data is unavailable")
            state: MarketState = "insufficient_data"
            trend = "unavailable"
        else:
            change = (benchmark[-1] / benchmark[0]) - 1
            trend = "uptrend" if change > 0 else "downtrend"
            state = self._state(change, breadth)
        volatility = self._volatility(benchmark)
        if volatility == "unavailable" and len(benchmark) >= 2:
            caveats.append("VNINDEX volatility requires at least three observations")
        quality = "complete" if volatility != "unavailable" else "partial"
        if state == "insufficient_data":
            quality = "insufficient_data"
        result: MarketRegime = {
            "as_of_date": date,
            "state": state,
            "trend": trend,
            "volatility": volatility,
            "breadth": breadth,
            "methodology": "market_regime_v1: VNINDEX return, return volatility, and daily symbol breadth from canonical OHLCV",
            "freshness": "as_of_date",
            "lineage": {"source": "canonical_ohlcv", "benchmark": "VNINDEX"},
            "quality": quality,
            "caveats": caveats,
        }
        self._conn.execute(
            """
            INSERT INTO market_regime_snapshot (date, state, analysis_json, generated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (date) DO UPDATE SET
                state = excluded.state, analysis_json = excluded.analysis_json,
                generated_at = excluded.generated_at
            """,
            [date, state, json.dumps(result), datetime.now(timezone.utc)],
        )
        log_audit(
            "MARKET_REGIME_BUILT",
            f"Market regime built for {date}: {state}",
            run_ctx=run_ctx,
            extra={"date": date, "state": state},
            module=__name__,
            function="MarketRegimeBuilder.build",
        )
        return result

    def _prices(self, symbol: str, date: str) -> list[float]:
        return [
            row[0]
            for row in self._conn.execute(
                """
                SELECT close FROM canonical_ohlcv
                WHERE symbol = ? AND interval = '1D' AND time::DATE <= ?
                ORDER BY time
                """,
                [symbol, date],
            ).fetchall()
            if row[0] is not None
        ]

    def _breadth(self, date: str) -> MarketBreadth:
        rows = self._conn.execute(
            """
            SELECT c.symbol, min_by(c.close, c.time), max_by(c.close, c.time)
            FROM canonical_ohlcv c JOIN symbol_master s USING (symbol)
            WHERE c.interval = '1D' AND c.time::DATE <= ?
              AND coalesce(s.sector, '') <> 'Index'
            GROUP BY c.symbol
            """,
            [date],
        ).fetchall()
        advancing = sum(
            1 for _, first, last in rows if first is not None and last > first
        )
        declining = sum(
            1 for _, first, last in rows if first is not None and last < first
        )
        return {
            "advancing_symbols": advancing,
            "declining_symbols": declining,
            "unchanged_symbols": len(rows) - advancing - declining,
        }

    def _volatility(self, prices: list[float]) -> str:
        if len(prices) < 3:
            return "unavailable"
        returns = [
            later / earlier - 1
            for earlier, later in zip(prices, prices[1:], strict=False)
        ]
        standard_deviation = statistics.pstdev(returns)
        if standard_deviation >= 0.02:
            return "elevated"
        if standard_deviation >= 0.01:
            return "moderate"
        return "low"

    def _state(self, change: float, breadth: MarketBreadth) -> MarketState:
        if (
            change > 0.03
            and breadth["advancing_symbols"] >= breadth["declining_symbols"]
        ):
            return "risk_on"
        if change > 0:
            return "constructive"
        if breadth["declining_symbols"] > breadth["advancing_symbols"]:
            return "risk_off"
        return "mixed"
