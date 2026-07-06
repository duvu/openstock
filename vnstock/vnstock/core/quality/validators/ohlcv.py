"""OHLCV validator.

Validates Open-High-Low-Close-Volume DataFrames against the standard
OHLCV contract defined in the data quality design.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnstock.core.quality.base import BaseValidator
from vnstock.core.quality.models import QualityIssue, ValidationReport
from vnstock.core.quality.rules import freshness as freshness_rules
from vnstock.core.quality.rules import numeric as numeric_rules
from vnstock.core.quality.rules import schema as schema_rules
from vnstock.core.quality.rules import temporal as temporal_rules

_REQUIRED_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
_PRICE_COLUMNS = ["open", "high", "low", "close"]
_VOLUME_COLUMNS = ["volume"]
_NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume"]


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


class OHLCVValidator(BaseValidator):
    """Validate OHLCV DataFrames.

    Checks performed (in order):

    1. Schema — required columns, empty DataFrame.
    2. Numeric — negative prices, negative volumes, null/NaN/inf.
    3. OHLC consistency — ``high >= low``, ``high >= open``,
       ``high >= close``, ``low <= open``, ``low <= close``.
    4. Temporal — parseable timestamps, duplicates, monotonic order,
       future timestamps.
    5. Freshness — staleness against configured threshold (when metadata
       is available).
    """

    dataset_type: str = "ohlcv"

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
            _classify(
                schema_rules.check_all_null_columns(df, _REQUIRED_COLUMNS, max_ex)
            )

            # 2. Numeric
            _classify(numeric_rules.check_negative_prices(df, _PRICE_COLUMNS, max_ex))
            _classify(numeric_rules.check_negative_volumes(df, _VOLUME_COLUMNS, max_ex))
            _classify(numeric_rules.check_null_nan_inf(df, _NUMERIC_COLUMNS, max_ex))
            if cfg.check_price_scale:
                _classify(
                    numeric_rules.check_price_scale(
                        df, _PRICE_COLUMNS, max_examples=max_ex
                    )
                )

            # 3. OHLC consistency
            if cfg.check_ohlc_consistency:
                _classify(_check_ohlc_consistency(df, max_ex))

            # 4. Temporal
            _classify(temporal_rules.check_datetime_parse(df, "time", max_ex))
            _classify(temporal_rules.check_duplicate_times(df, "time", max_ex))
            _classify(temporal_rules.check_monotonic_time(df, "time", max_ex))
            _classify(
                temporal_rules.check_future_times(df, "time", max_examples=max_ex)
            )

        # 5. Freshness
        _classify(
            freshness_rules.check_stale_daily_ohlcv(
                df, cfg.stale_daily_ohlcv_hours, time_column="time"
            )
        )

        # Build report
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


def _check_ohlc_consistency(
    df: pd.DataFrame, max_examples: int = 20
) -> list[QualityIssue]:
    """Check OHLC consistency rules; all required columns must be present."""
    issues: list[QualityIssue] = []
    required = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        return issues

    h = pd.to_numeric(df["high"], errors="coerce")
    l = pd.to_numeric(df["low"], errors="coerce")  # noqa: E741
    o = pd.to_numeric(df["open"], errors="coerce")
    c = pd.to_numeric(df["close"], errors="coerce")

    checks = [
        ("high", "low", h < l, "OHLC_HIGH_BELOW_LOW", "high < low"),
        ("high", "open", h < o, "OHLC_HIGH_BELOW_OPEN", "high < open"),
        ("high", "close", h < c, "OHLC_HIGH_BELOW_CLOSE", "high < close"),
        ("low", "open", l > o, "OHLC_LOW_ABOVE_OPEN", "low > open"),
        ("low", "close", l > c, "OHLC_LOW_ABOVE_CLOSE", "low > close"),
    ]

    for col_a, col_b, mask, code, label in checks:
        for idx in df.index[mask.fillna(False)][:max_examples]:
            issues.append(
                QualityIssue(
                    code=code,
                    severity="error",
                    message=f"OHLC inconsistency: {label} at row {idx}.",
                    column=col_a,
                    row_index=_safe_positional_index(df, idx),
                    context={col_a: df.at[idx, col_a], col_b: df.at[idx, col_b]},
                )
            )
            if len(issues) >= max_examples:
                return issues
    return issues
