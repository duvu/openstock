"""
KBS normalizer: converts provider-native DataFrames to dataset contract shape.

KBS already returns fairly clean DataFrames.  Normalization here ensures
required columns exist and adds a 'symbol' column where missing.
"""

from __future__ import annotations

import pandas as pd

from vnstock.core.provider.exceptions import ProviderFetchError

_OHLCV_REQUIRED = ["time", "open", "high", "low", "close", "volume"]


def normalize_equity_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Normalize KBS OHLCV response to equity.ohlcv contract.

    Args:
        df: Raw DataFrame from KBS Quote.history().
        symbol: Stock ticker symbol.

    Returns:
        DataFrame with columns: symbol, time, open, high, low, close, volume.

    Raises:
        ProviderFetchError: If required columns are missing.
    """
    missing = [c for c in _OHLCV_REQUIRED if c not in df.columns]
    if missing:
        raise ProviderFetchError(
            "KBS",
            "equity.ohlcv",
            cause=ValueError(f"Missing required columns: {missing}"),
        )
    df = df.copy()
    if "symbol" not in df.columns:
        df.insert(0, "symbol", symbol)
    # Ensure time is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"])
    # Ensure numeric columns
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def normalize_equity_quote(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Normalize KBS price board to equity.quote contract.

    Args:
        df: Raw DataFrame from KBS Trading.price_board().
        symbol: Optional symbol override.

    Returns:
        DataFrame with columns: symbol, close_price, volume_accumulated.
    """
    df = df.copy()
    # Map common KBS column names → contract names
    rename_map: dict[str, str] = {}
    if "ticker" in df.columns and "symbol" not in df.columns:
        rename_map["ticker"] = "symbol"
    if "match_price" in df.columns and "close_price" not in df.columns:
        rename_map["match_price"] = "close_price"
    if "total_volume" in df.columns and "volume_accumulated" not in df.columns:
        rename_map["total_volume"] = "volume_accumulated"
    if rename_map:
        df = df.rename(columns=rename_map)
    if symbol and "symbol" not in df.columns:
        df.insert(0, "symbol", symbol)
    return df
