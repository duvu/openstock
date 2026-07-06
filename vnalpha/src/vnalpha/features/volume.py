"""Volume features."""

from __future__ import annotations

import pandas as pd


def compute_volume_ma(volume: pd.Series, window: int = 20) -> pd.Series:
    """Volume moving average."""
    return volume.rolling(window, min_periods=window).mean()


def compute_volume_ratio(volume: pd.Series, volume_ma: pd.Series) -> pd.Series:
    """Ratio of current volume to volume MA."""
    return volume / volume_ma.where(volume_ma != 0, other=float("nan"))


def compute_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all volume features."""
    df = df.copy()
    df["volume_ma20"] = compute_volume_ma(df["volume"], 20)
    df["volume_ratio"] = compute_volume_ratio(df["volume"], df["volume_ma20"])
    return df
