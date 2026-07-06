"""Intraday trade validator.

Validates DataFrames representing intraday trade tick data against the
standard intraday trades contract defined in the data quality design.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnstock.core.quality.base import BaseValidator
from vnstock.core.quality.models import QualityIssue, ValidationReport
from vnstock.core.quality.rules import freshness as freshness_rules
from vnstock.core.quality.rules import schema as schema_rules

_REQUIRED_COLUMNS = ["time", "price", "volume", "match_type", "id"]
_VALID_MATCH_TYPES = frozenset({"buy", "sell", "unknown", "ato", "atc"})

# Market session: HOSE 09:00 – 14:30 (ICT, UTC+7)
_SESSION_OPEN_HOUR = 9
_SESSION_OPEN_MINUTE = 0
_SESSION_CLOSE_HOUR = 14
_SESSION_CLOSE_MINUTE = 30


def _safe_positional_index(df, label_index):
    """Return 0-based positional index for label_index; avoids int() crash on non-int indices."""
    try:
        loc = df.index.get_loc(label_index)
        if isinstance(loc, int):
            return loc
        # Duplicate labels: get_loc returns slice or boolean ndarray
        if isinstance(loc, slice):
            # Return the start of the slice (first matching position)
            return loc.start if loc.start is not None else 0
        # Boolean ndarray
        if hasattr(loc, "nonzero"):
            nz = loc.nonzero()[0]
            return int(nz[0]) if len(nz) > 0 else None
        return None
    except Exception:
        try:
            return int(label_index)
        except (TypeError, ValueError):
            return None


class IntradayValidator(BaseValidator):
    """Validate intraday trade tick DataFrames.

    Checks performed (in order):

    1. Schema — required columns, empty DataFrame.
    2. Match type enum validation.
    3. Duplicate trade IDs.
    4. Positive prices.
    5. Non-negative volumes.
    6. Optional market session time validation.
    7. Freshness.
    """

    dataset_type: str = "intraday_trades"

    def validate(
        self,
        df: pd.DataFrame,
        provider: str | None = None,
        symbol: str | None = None,
        interval: str | None = None,
        config: Any | None = None,
    ) -> ValidationReport:
        from vnstock.core.settings import QualityConfig

        cfg: QualityConfig = config if config is not None else QualityConfig()
        max_ex = cfg.max_error_examples

        errors: list[QualityIssue] = []
        warnings: list[QualityIssue] = []
        infos: list[QualityIssue] = []

        def _classify(issues: list[QualityIssue]) -> None:
            for iss in issues:
                if iss.severity == "error":
                    errors.append(iss)
                elif iss.severity == "warning":
                    warnings.append(iss)
                else:
                    infos.append(iss)

        # 1. Schema
        _classify(schema_rules.check_required_columns(df, _REQUIRED_COLUMNS))
        _classify(schema_rules.check_empty_dataframe(df))

        if not df.empty:
            # 2. Match type
            _classify(_check_match_type(df, max_ex))

            # 3. Duplicate IDs
            _classify(_check_duplicate_ids(df, max_ex))

            # 4. Positive prices
            _classify(_check_positive_prices(df, max_ex))

            # 5. Non-negative volumes
            _classify(_check_non_negative_volumes(df, max_ex))

            # 6. Optional session time
            if cfg.check_session_time:
                _classify(_check_session_time(df, max_ex))

        # 7. Freshness
        _classify(freshness_rules.check_stale_intraday(df, cfg.stale_intraday_seconds))

        # Latest time
        latest_time: str | None = None
        freshness_status = "unknown"
        if not df.empty and "time" in df.columns:
            parsed = pd.to_datetime(df["time"], errors="coerce", utc=True)
            valid = parsed.dropna()
            if not valid.empty:
                latest_time = str(valid.max().isoformat())
                freshness_status = (
                    "fresh"
                    if not any(i.code == "FRESHNESS_STALE" for i in warnings)
                    else "stale"
                )

        return ValidationReport(
            valid=len(errors) == 0,
            dataset_type=self.dataset_type,
            provider=provider,
            symbol=symbol,
            interval=interval,
            row_count=len(df),
            latest_time=latest_time,
            freshness_status=freshness_status,
            errors=errors,
            warnings=warnings,
            infos=infos,
        )


def _check_match_type(df: pd.DataFrame, max_examples: int = 20) -> list[QualityIssue]:
    if "match_type" not in df.columns:
        return []
    issues: list[QualityIssue] = []
    invalid_mask = ~df["match_type"].astype(str).str.lower().isin(_VALID_MATCH_TYPES)
    for idx in df.index[invalid_mask][:max_examples]:
        issues.append(
            QualityIssue(
                code="TRADE_INVALID_MATCH_TYPE",
                severity="error",
                message=(
                    f"match_type '{df.at[idx, 'match_type']}' is not one of "
                    f"{sorted(_VALID_MATCH_TYPES)}."
                ),
                column="match_type",
                row_index=_safe_positional_index(df, idx),
                value=str(df.at[idx, "match_type"]),
            )
        )
    return issues


def _check_duplicate_ids(
    df: pd.DataFrame, max_examples: int = 20
) -> list[QualityIssue]:
    if "id" not in df.columns:
        return []
    issues: list[QualityIssue] = []
    # Check for duplicate non-null IDs
    non_null = df["id"].notna()
    dup_mask = df["id"].duplicated(keep="first") & non_null
    for idx in df.index[dup_mask][:max_examples]:
        issues.append(
            QualityIssue(
                code="TRADE_DUPLICATE_ID",
                severity="warning",
                message=f"Duplicate trade id '{df.at[idx, 'id']}' at row {idx}.",
                column="id",
                row_index=_safe_positional_index(df, idx),
                value=str(df.at[idx, "id"]),
            )
        )
    return issues


def _check_positive_prices(
    df: pd.DataFrame, max_examples: int = 20
) -> list[QualityIssue]:
    if "price" not in df.columns:
        return []
    issues: list[QualityIssue] = []
    price = pd.to_numeric(df["price"], errors="coerce")
    non_positive = price <= 0
    for idx in df.index[non_positive & price.notna()][:max_examples]:
        issues.append(
            QualityIssue(
                code="TRADE_NON_POSITIVE_PRICE",
                severity="error",
                message=f"Trade price must be positive; got {df.at[idx, 'price']} at row {idx}.",
                column="price",
                row_index=_safe_positional_index(df, idx),
                value=df.at[idx, "price"],
            )
        )
    return issues


def _check_non_negative_volumes(
    df: pd.DataFrame, max_examples: int = 20
) -> list[QualityIssue]:
    if "volume" not in df.columns:
        return []
    issues: list[QualityIssue] = []
    vol = pd.to_numeric(df["volume"], errors="coerce")
    neg_mask = vol < 0
    for idx in df.index[neg_mask & vol.notna()][:max_examples]:
        issues.append(
            QualityIssue(
                code="TRADE_NEGATIVE_VOLUME",
                severity="error",
                message=f"Trade volume must be non-negative; got {df.at[idx, 'volume']} at row {idx}.",
                column="volume",
                row_index=_safe_positional_index(df, idx),
                value=df.at[idx, "volume"],
            )
        )
    return issues


def _check_session_time(df: pd.DataFrame, max_examples: int = 20) -> list[QualityIssue]:
    """Warn when trade times fall outside the HOSE market session (09:00–14:30 ICT)."""
    if "time" not in df.columns:
        return []
    issues: list[QualityIssue] = []
    parsed = pd.to_datetime(df["time"], errors="coerce")

    # Normalise to Asia/Ho_Chi_Minh for session boundary comparison.
    # - tz-aware timestamps: convert explicitly.
    # - tz-naive timestamps: treat as local (Asia/Ho_Chi_Minh) without shift.
    if parsed.dt.tz is not None:
        try:
            parsed = parsed.dt.tz_convert("Asia/Ho_Chi_Minh")
        except Exception:
            parsed = parsed.dt.tz_localize(None)
    # (tz-naive stays as-is; assumed to be local Vietnam time already)

    session_open = parsed.dt.hour * 60 + parsed.dt.minute
    open_minutes = _SESSION_OPEN_HOUR * 60 + _SESSION_OPEN_MINUTE
    close_minutes = _SESSION_CLOSE_HOUR * 60 + _SESSION_CLOSE_MINUTE
    outside = (session_open < open_minutes) | (session_open > close_minutes)
    outside = outside & parsed.notna()
    for idx in df.index[outside][:max_examples]:
        issues.append(
            QualityIssue(
                code="TRADE_TIME_OUTSIDE_SESSION",
                severity="warning",
                message=f"Trade time {df.at[idx, 'time']} is outside the market session.",
                column="time",
                row_index=_safe_positional_index(df, idx),
                value=str(df.at[idx, "time"]),
            )
        )
    return issues
