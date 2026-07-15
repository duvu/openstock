from __future__ import annotations

import pandas as pd

from vnstock.providers.fiinquantx.exceptions import FiinQuantXSchemaError

_OHLCV_COLUMNS = ("ticker", "timestamp", "open", "high", "low", "close", "volume")
_NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume", "value")


def normalize_ohlcv(frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
    missing = [column for column in _OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise FiinQuantXSchemaError(dataset)
    normalized = frame.copy().rename(columns={"ticker": "symbol", "timestamp": "time"})
    try:
        normalized["time"] = pd.to_datetime(normalized["time"], errors="raise")
        for column in _NUMERIC_COLUMNS:
            if column in normalized.columns:
                normalized[column] = pd.to_numeric(normalized[column], errors="raise")
    except (TypeError, ValueError):
        raise FiinQuantXSchemaError(dataset) from None
    columns = ["symbol", "time", "open", "high", "low", "close", "volume"]
    if "value" in normalized.columns:
        columns.append("value")
    return normalized.loc[:, columns]


def normalize_membership(members: list[str], entity_id: str) -> pd.DataFrame:
    normalized_members = [member.upper() for member in members if member]
    return pd.DataFrame(
        {
            "entity_id": entity_id.upper(),
            "member_symbol": normalized_members,
            "observed_at": pd.Timestamp.now(tz="UTC").tz_localize(None),
        }
    )
