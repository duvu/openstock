"""Volatility features: ATR14, volatility_20d."""
from __future__ import annotations
import pandas as pd
import numpy as np


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Compute Average True Range (ATR)."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def compute_volatility(close: pd.Series, period: int = 20) -> pd.Series:
    """Compute rolling standard deviation of log returns."""
    log_returns = np.log(close / close.shift(1))
    return log_returns.rolling(period, min_periods=period).std()


def compute_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute ATR14 and volatility_20d."""
    df = df.copy()
    df["atr14"] = compute_atr(df["high"], df["low"], df["close"], 14)
    df["volatility_20d"] = compute_volatility(df["close"], 20)
    return df
