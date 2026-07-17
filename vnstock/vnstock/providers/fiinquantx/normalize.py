from __future__ import annotations

from collections.abc import Iterable
import re

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
_FIELD_ALIASES = {
    "ticker": (
        "ticker",
        "symbol",
        "stock",
        "code",
        "symbolcode",
        "maticker",
    ),
    "timestamp": (
        "timestamp",
        "time",
        "datetime",
        "tradingdate",
        "trading_date",
        "date",
    ),
    "open": ("open", "openprice", "open_price", "o"),
    "high": ("high", "highprice", "high_price", "h"),
    "low": ("low", "lowprice", "low_price", "l"),
    "close": ("close", "closeprice", "close_price", "c"),
    "volume": ("volume", "vol", "volumeaccumulated", "v"),
    "value": ("value", "valueamount", "tradevalue", "matchedvalue", "val"),
}


def _normalize_field_name(name: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).strip().lower())


def _canonicalize_ohlcv_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized_column_names = {_normalize_field_name(col): col for col in frame.columns}
    rename_map: dict[str, str] = {}
    for canonical, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize_field_name(alias)
            source = normalized_column_names.get(normalized_alias)
            if source is not None:
                rename_map[source] = canonical
                break
    if rename_map:
        frame = frame.rename(columns=rename_map)
    return frame


def _normalize_timestamp(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dt.tz_convert(None)
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="raise")
        if numeric.empty:
            return pd.to_datetime([], unit="s", utc=True).tz_convert(None)
        max_value = abs(int(numeric.max()))
        if max_value >= 10**15:
            unit = "ns"
        elif max_value >= 10**12:
            unit = "ms"
        elif max_value >= 10**10:
            unit = "s"
        else:
            unit = "ms"
        return pd.to_datetime(numeric, unit=unit, utc=True).dt.tz_convert(None)
    return pd.to_datetime(series, errors="raise", utc=True).dt.tz_convert(None)


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
    frame = _canonicalize_ohlcv_columns(frame)
    missing = [column for column in _OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise FiinQuantXSchemaError(dataset)
    normalized = frame.copy().rename(columns={"ticker": "symbol", "timestamp": "time"})
    try:
        normalized["symbol"] = normalized["symbol"].astype("string").str.upper()
        normalized["time"] = _normalize_timestamp(normalized["time"])
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
