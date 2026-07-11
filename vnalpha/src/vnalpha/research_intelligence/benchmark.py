"""Benchmark feature context for market-regime snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite, sqrt
from typing import Final, Literal

import duckdb
import pandas as pd

from vnalpha.features.build_features import (
    build_features_for_symbol,
    load_canonical_ohlcv,
)

MINIMUM_BENCHMARK_BARS: Final = 60
HIGH_VOLATILITY_THRESHOLD: Final = 0.30 / sqrt(252)
Trend = Literal["UPTREND", "DOWNTREND", "MIXED", "INSUFFICIENT_DATA"]
Volatility = Literal["HIGH", "NORMAL", "INSUFFICIENT_DATA"]


@dataclass(frozen=True, slots=True)
class BenchmarkContext:
    bar_date: date
    row_count: int
    close: float
    ma20: float
    ma50: float
    ma50_slope: float
    return20: float | None
    return60: float | None
    volatility20: float
    freshness: str
    trend: Trend
    volatility: Volatility
    caveats: tuple[str, ...]

    @property
    def available(self) -> bool:
        """Whether the benchmark supplies every required regime dimension."""
        return (
            self.row_count >= MINIMUM_BENCHMARK_BARS
            and self.trend != "INSUFFICIENT_DATA"
            and self.volatility != "INSUFFICIENT_DATA"
        )


def _as_float(value: float | int | None) -> float:
    """Normalize an optional metric to the required snapshot field type."""
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def _as_optional_float(value: float | int | None) -> float | None:
    """Preserve an unavailable optional return metric as null."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def _required_values_available(values: tuple[float | int | None, ...]) -> bool:
    """Check the feature dimensions required for trend and volatility context."""
    return all(
        value is not None and not pd.isna(value) and isfinite(float(value))
        for value in values
    )


def classify_trend(
    close: float,
    ma20: float,
    ma50: float,
    ma50_slope: float,
    *,
    required_values_available: bool,
) -> Trend:
    """Classify trend from required close, moving-average, and slope inputs."""
    if not required_values_available:
        return "INSUFFICIENT_DATA"
    if close > ma20 > ma50 and ma50_slope > 0:
        return "UPTREND"
    if close < ma20 < ma50 and ma50_slope < 0:
        return "DOWNTREND"
    return "MIXED"


def classify_volatility(
    volatility20: float,
    *,
    required_values_available: bool,
) -> Volatility:
    """Classify daily volatility against the annualized thirty-percent boundary."""
    if not required_values_available:
        return "INSUFFICIENT_DATA"
    if volatility20 >= HIGH_VOLATILITY_THRESHOLD:
        return "HIGH"
    return "NORMAL"


def load_benchmark_context(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    benchmark_symbol: str,
) -> BenchmarkContext:
    """Load canonical benchmark data and derive its regime feature context."""
    benchmark = load_canonical_ohlcv(conn, benchmark_symbol, as_of_date.isoformat())
    if benchmark.empty:
        return BenchmarkContext(
            bar_date=as_of_date,
            row_count=0,
            close=0.0,
            ma20=0.0,
            ma50=0.0,
            ma50_slope=0.0,
            return20=None,
            return60=None,
            volatility20=0.0,
            freshness="MISSING",
            trend="INSUFFICIENT_DATA",
            volatility="INSUFFICIENT_DATA",
            caveats=(f"Benchmark {benchmark_symbol} is unavailable.",),
        )
    features = build_features_for_symbol(benchmark)
    bar_date = benchmark.index[-1].date()
    freshness = "EXACT_DATE" if bar_date == as_of_date else "STALE_DATE"
    if len(benchmark) < MINIMUM_BENCHMARK_BARS or features.empty:
        return BenchmarkContext(
            bar_date=bar_date,
            row_count=len(benchmark),
            close=0.0,
            ma20=0.0,
            ma50=0.0,
            ma50_slope=0.0,
            return20=None,
            return60=None,
            volatility20=0.0,
            freshness=freshness,
            trend="INSUFFICIENT_DATA",
            volatility="INSUFFICIENT_DATA",
            caveats=(
                f"Benchmark history has {len(benchmark)} bars; "
                f"{MINIMUM_BENCHMARK_BARS} required.",
            ),
        )
    row = features.iloc[-1]
    values = tuple(
        _as_float(row[name])
        for name in ("close", "ma20", "ma50", "ma50_slope", "volatility_20d")
    )
    return20 = _as_optional_float(row["return_20d"])
    return60 = _as_optional_float(row["return_60d"])
    required_available = _required_values_available(
        tuple(
            row[name]
            for name in ("close", "ma20", "ma50", "ma50_slope", "volatility_20d")
        )
    )
    caveats = []
    if freshness != "EXACT_DATE":
        caveats.append("Benchmark bar is stale.")
    if not required_available:
        caveats.append("Required benchmark feature values are unavailable.")
    if return20 is None:
        caveats.append("Benchmark 20-session return is unavailable.")
    if return60 is None:
        caveats.append("Benchmark 60-session return is unavailable.")
    return BenchmarkContext(
        bar_date=bar_date,
        row_count=len(benchmark),
        close=values[0],
        ma20=values[1],
        ma50=values[2],
        ma50_slope=values[3],
        return20=return20,
        return60=return60,
        volatility20=values[4],
        freshness=freshness,
        trend=classify_trend(
            values[0],
            values[1],
            values[2],
            values[3],
            required_values_available=required_available,
        ),
        volatility=classify_volatility(
            values[4],
            required_values_available=required_available,
        ),
        caveats=tuple(caveats),
    )
