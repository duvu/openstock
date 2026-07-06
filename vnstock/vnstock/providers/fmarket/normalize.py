"""
FMarket normalizer: converts provider-native DataFrames to dataset contract shape.
"""

from __future__ import annotations

import pandas as pd

from vnstock.core.provider.exceptions import ProviderFetchError

_NAV_REQUIRED = ["fund_id", "nav", "nav_date"]


def normalize_fund_nav(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize FMarket NAV response to fund.nav contract."""
    missing = [c for c in _NAV_REQUIRED if c not in df.columns]
    if missing:
        raise ProviderFetchError(
            "FMARKET",
            "fund.nav",
            cause=ValueError(f"Missing required columns: {missing}"),
        )
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["nav_date"]):
        df["nav_date"] = pd.to_datetime(df["nav_date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    return df
