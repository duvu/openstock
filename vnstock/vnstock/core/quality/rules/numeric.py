"""Numeric validation rules for market data DataFrames.

Each function accepts a DataFrame (or column Series) and returns a list of
:class:`~vnstock.core.quality.models.QualityIssue` objects.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vnstock.core.quality.models import QualityIssue

# Heuristic: Vietnamese equities trade between 1_000 and 200_000 VND.
# Anything below 100 VND or above 200_000_000 VND (200M) is suspicious.
_PRICE_SCALE_MIN = 100.0
_PRICE_SCALE_MAX = 200_000_000.0


def _safe_positional_index(df, label_index):
    """Return 0-based positional index for label_index; avoids int() crash on non-int indices."""
    try:
        loc = df.index.get_loc(label_index)
        if isinstance(loc, int):
            return loc
        # Duplicate labels: get_loc returns slice or boolean ndarray
        if isinstance(loc, slice):
            return loc.start if loc.start is not None else 0
        if hasattr(loc, "nonzero"):
            nz = loc.nonzero()[0]
            return int(nz[0]) if len(nz) > 0 else None
        return None
    except Exception:
        try:
            return int(label_index)
        except (TypeError, ValueError):
            return None


def check_negative_prices(
    df: pd.DataFrame,
    price_columns: list[str],
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return error issues for rows where price columns are negative.

    Args:
        df: DataFrame to inspect.
        price_columns: List of column names expected to be non-negative prices.
        max_examples: Maximum total number of issues to return.

    Returns:
        List of :class:`QualityIssue` with code ``NUMERIC_NEGATIVE_PRICE``.
    """
    issues: list[QualityIssue] = []
    for col in price_columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        mask = series < 0
        for idx in df.index[mask][:max_examples]:
            issues.append(
                QualityIssue(
                    code="NUMERIC_NEGATIVE_PRICE",
                    severity="error",
                    message=f"Column '{col}' has a negative price value.",
                    column=col,
                    row_index=_safe_positional_index(df, idx),
                    value=df.at[idx, col],
                )
            )
            if len(issues) >= max_examples:
                return issues
    return issues


def check_negative_volumes(
    df: pd.DataFrame,
    volume_columns: list[str],
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return error issues for rows where volume columns are negative.

    Args:
        df: DataFrame to inspect.
        volume_columns: List of column names expected to be non-negative volumes.
        max_examples: Maximum total number of issues to return.

    Returns:
        List of :class:`QualityIssue` with code ``NUMERIC_NEGATIVE_VOLUME``.
    """
    issues: list[QualityIssue] = []
    for col in volume_columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        mask = series < 0
        for idx in df.index[mask][:max_examples]:
            issues.append(
                QualityIssue(
                    code="NUMERIC_NEGATIVE_VOLUME",
                    severity="error",
                    message=f"Column '{col}' has a negative volume value.",
                    column=col,
                    row_index=_safe_positional_index(df, idx),
                    value=df.at[idx, col],
                )
            )
            if len(issues) >= max_examples:
                return issues
    return issues


def check_null_nan_inf(
    df: pd.DataFrame,
    columns: list[str],
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return issues for null, NaN, and infinite values in numeric columns.

    Issues:
    * ``NUMERIC_NULL_VALUE`` — missing / NaN
    * ``NUMERIC_INF_VALUE`` — positive or negative infinity

    Args:
        df: DataFrame to inspect.
        columns: List of column names to check.
        max_examples: Maximum total number of issues to return.

    Returns:
        List of :class:`QualityIssue`.
    """
    issues: list[QualityIssue] = []
    for col in columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        null_mask = series.isna()
        inf_mask = np.isinf(series.fillna(0))

        for idx in df.index[null_mask][:max_examples]:
            issues.append(
                QualityIssue(
                    code="NUMERIC_NULL_VALUE",
                    severity="warning",
                    message=f"Column '{col}' has a null/NaN value.",
                    column=col,
                    row_index=_safe_positional_index(df, idx),
                )
            )
            if len(issues) >= max_examples:
                return issues

        for idx in df.index[inf_mask][:max_examples]:
            issues.append(
                QualityIssue(
                    code="NUMERIC_INF_VALUE",
                    severity="error",
                    message=f"Column '{col}' has an infinite value.",
                    column=col,
                    row_index=_safe_positional_index(df, idx),
                    value=df.at[idx, col],
                )
            )
            if len(issues) >= max_examples:
                return issues
    return issues


def check_price_scale(
    df: pd.DataFrame,
    price_columns: list[str],
    scale_min: float = _PRICE_SCALE_MIN,
    scale_max: float = _PRICE_SCALE_MAX,
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return warning issues when price values are outside the plausible range.

    Default thresholds target Vietnamese equity prices (100 – 200,000,000 VND).
    Pass explicit ``scale_min`` / ``scale_max`` to override.

    Args:
        df: DataFrame to inspect.
        price_columns: List of column names to check.
        scale_min: Minimum plausible positive price.
        scale_max: Maximum plausible price.
        max_examples: Maximum total number of issues to return.

    Returns:
        List of :class:`QualityIssue` with code ``OHLC_PRICE_SCALE_SUSPICIOUS``.
    """
    issues: list[QualityIssue] = []
    for col in price_columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        # Only flag positive values outside range (negatives caught elsewhere)
        mask = (series > 0) & ((series < scale_min) | (series > scale_max))
        for idx in df.index[mask][:max_examples]:
            val = series.at[idx]
            issues.append(
                QualityIssue(
                    code="OHLC_PRICE_SCALE_SUSPICIOUS",
                    severity="warning",
                    message=(
                        f"Column '{col}' value {val} is outside the expected "
                        f"price range [{scale_min}, {scale_max}]."
                    ),
                    column=col,
                    row_index=_safe_positional_index(df, idx),
                    value=float(val),
                    context={"scale_min": scale_min, "scale_max": scale_max},
                )
            )
            if len(issues) >= max_examples:
                return issues
    return issues
