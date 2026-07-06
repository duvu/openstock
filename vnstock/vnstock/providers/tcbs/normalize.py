"""
TCBS normalizer: converts provider-native DataFrames to dataset contract shape.
"""

from __future__ import annotations

import pandas as pd

from vnstock.core.provider.exceptions import ProviderFetchError

_OHLCV_REQUIRED = ["time", "open", "high", "low", "close", "volume"]


def normalize_equity_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Normalize TCBS OHLCV response to equity.ohlcv contract."""
    missing = [c for c in _OHLCV_REQUIRED if c not in df.columns]
    if missing:
        raise ProviderFetchError(
            "TCBS",
            "equity.ohlcv",
            cause=ValueError(f"Missing required columns: {missing}"),
        )
    df = df.copy()
    if "symbol" not in df.columns:
        df.insert(0, "symbol", symbol)
    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
