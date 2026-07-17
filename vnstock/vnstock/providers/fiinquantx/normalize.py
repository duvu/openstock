from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from vnstock.providers.fiinquantx.exceptions import FiinQuantXSchemaError

_OHLCV_COLUMNS = ("ticker", "timestamp", "open", "high", "low", "close", "volume")
_NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume", "value")
_CANONICAL_OHLCV_COLUMNS = (
    "symbol",
    "time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "value",
)


def _empty_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": pd.Series(dtype="string"),
            "time": pd.Series(dtype="datetime64[ns]"),
            "open": pd.Series(dtype="float64"),
            "high": pd.Series(dtype="float64"),
            "low": pd.Series(dtype="float64"),
            "close": pd.Series(dtype="float64"),
            "volume": pd.Series(dtype="float64"),
            "value": pd.Series(dtype="float64"),
        }
    )


def normalize_ohlcv(frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise FiinQuantXSchemaError(dataset)
    if frame.empty and not set(_OHLCV_COLUMNS).issubset(frame.columns):
        return _empty_ohlcv()
    missing = [column for column in _OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise FiinQuantXSchemaError(dataset)
    normalized = frame.copy().rename(columns={"ticker": "symbol", "timestamp": "time"})
    try:
        normalized["symbol"] = normalized["symbol"].astype("string").str.upper()
        normalized["time"] = pd.to_datetime(
            normalized["time"], errors="raise", utc=True
        ).dt.tz_convert(None)
        for column in _NUMERIC_COLUMNS:
            if column in normalized.columns:
                normalized[column] = pd.to_numeric(normalized[column], errors="raise")
    except (AttributeError, TypeError, ValueError):
        raise FiinQuantXSchemaError(dataset) from None
    columns = [
        "symbol",
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    if "value" in normalized.columns:
        columns.append("value")
    normalized = normalized.loc[:, columns]
    if "value" not in normalized.columns:
        normalized["value"] = pd.Series(index=normalized.index, dtype="float64")
    normalized = normalized.loc[:, list(_CANONICAL_OHLCV_COLUMNS)]
    normalized = normalized.sort_values(["symbol", "time"])
    normalized = normalized.drop_duplicates(["symbol", "time"], keep="last")
    normalized = normalized.reset_index(drop=True)
    normalized.attrs = {}
    return normalized


def normalize_membership(members: Iterable[str], entity_id: str) -> pd.DataFrame:
    normalized_members = list(
        dict.fromkeys(str(member).strip().upper() for member in members if member)
    )
    observed_at = pd.Timestamp.now(tz="UTC")
    row_count = len(normalized_members)
    return pd.DataFrame(
        {
            "entity_id": pd.Series(
                [entity_id.upper()] * row_count,
                dtype="string",
            ),
            "member_symbol": pd.Series(normalized_members, dtype="string"),
            "observed_at": pd.Series(
                [observed_at] * row_count,
                dtype="datetime64[ns, UTC]",
            ),
        }
    )
