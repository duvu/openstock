"""Price trend features: moving averages and slopes."""

from __future__ import annotations

import pandas as pd


def compute_ma(series: pd.Series, window: int) -> pd.Series:
    """Compute simple moving average."""
    return series.rolling(window, min_periods=window).mean()


def compute_ma_slope(ma_series: pd.Series, period: int = 5) -> pd.Series:
    """Compute slope as (last - first) / first over a rolling period."""

    def _slope(x: pd.Series) -> float:
        if x.isna().any() or x.iloc[0] == 0:
            return float("nan")
        return (x.iloc[-1] - x.iloc[0]) / x.iloc[0]

    return ma_series.rolling(period, min_periods=period).apply(_slope, raw=False)


def compute_distance_to_ma(close: pd.Series, ma: pd.Series) -> pd.Series:
    """Distance from close to MA as (close - MA) / MA."""
    return (close - ma) / ma.where(ma != 0, other=float("nan"))


def compute_distance_to_52w_high(close: pd.Series) -> pd.Series:
    """Distance from close to 52-week (252-day) rolling high."""
    high_52w = close.rolling(252, min_periods=20).max()
    return (close - high_52w) / high_52w.where(high_52w != 0, other=float("nan"))


def compute_return(close: pd.Series, period: int) -> pd.Series:
    """Compute n-period return: (close / close.shift(n)) - 1."""
    return close / close.shift(period) - 1


def compute_close_strength(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
) -> pd.Series:
    """Compute close strength: (close - low) / (high - low) range 0-1."""
    rng = high - low
    return (close - low) / rng.where(rng != 0, other=float("nan"))


def compute_base_range(close: pd.Series, period: int = 30) -> pd.Series:
    """Compute base/compression range: (max - min) / mean over period."""
    rolling_max = close.rolling(period, min_periods=period).max()
    rolling_min = close.rolling(period, min_periods=period).min()
    rolling_mean = close.rolling(period, min_periods=period).mean()
    return (rolling_max - rolling_min) / rolling_mean.where(
        rolling_mean != 0, other=float("nan")
    )


def compute_price_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all price features on a OHLCV DataFrame.

    Args:
        df: DataFrame with columns: time (index), open, high, low, close, volume

    Returns:
        DataFrame with added feature columns.
    """
    df = df.copy()
    df["ma20"] = compute_ma(df["close"], 20)
    df["ma50"] = compute_ma(df["close"], 50)
    df["ma100"] = compute_ma(df["close"], 100)
    df["ma20_slope"] = compute_ma_slope(df["ma20"])
    df["ma50_slope"] = compute_ma_slope(df["ma50"])
    df["distance_to_ma20"] = compute_distance_to_ma(df["close"], df["ma20"])
    df["distance_to_52w_high"] = compute_distance_to_52w_high(df["close"])
    df["return_20d"] = compute_return(df["close"], 20)
    df["return_60d"] = compute_return(df["close"], 60)
    df["close_strength"] = compute_close_strength(df["close"], df["high"], df["low"])
    df["base_range_30d"] = compute_base_range(df["close"], 30)
    return df
