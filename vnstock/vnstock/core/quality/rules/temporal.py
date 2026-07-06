"""Temporal validation rules for market data DataFrames.

Each function inspects the time column and returns a list of
:class:`~vnstock.core.quality.models.QualityIssue` objects.
"""

from __future__ import annotations

import warnings

import pandas as pd

from vnstock.core.quality.models import QualityIssue


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


def _parse_time_series(series: pd.Series) -> pd.Series:
    """Coerce *series* to datetime, returning NaT for unparseable values."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(series, errors="coerce", utc=False)


def check_datetime_parse(
    df: pd.DataFrame,
    time_column: str = "time",
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return error issues for rows where the time column cannot be parsed.

    Args:
        df: DataFrame to inspect.
        time_column: Name of the time column.
        max_examples: Maximum number of issues to return.

    Returns:
        Issues with codes ``TIME_MISSING`` (null) or ``TIME_INVALID`` (unparseable).
    """
    issues: list[QualityIssue] = []
    if time_column not in df.columns:
        return issues

    parsed = _parse_time_series(df[time_column])
    # Identify rows that were originally non-null but failed to parse
    originally_null = df[time_column].isna()
    parse_failed = (~originally_null) & parsed.isna()

    for idx in df.index[originally_null][:max_examples]:
        issues.append(
            QualityIssue(
                code="TIME_MISSING",
                severity="warning",
                message=f"Column '{time_column}' is null at row {idx}.",
                column=time_column,
                row_index=_safe_positional_index(df, idx),
            )
        )
    for idx in df.index[parse_failed][:max_examples]:
        issues.append(
            QualityIssue(
                code="TIME_INVALID",
                severity="error",
                message=f"Column '{time_column}' could not be parsed as datetime at row {idx}.",
                column=time_column,
                row_index=_safe_positional_index(df, idx),
                value=str(df.at[idx, time_column]),
            )
        )
    return issues[:max_examples]


def check_duplicate_times(
    df: pd.DataFrame,
    time_column: str = "time",
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return warning issues for duplicate values in the time column.

    Args:
        df: DataFrame to inspect.
        time_column: Name of the time column.
        max_examples: Maximum number of issues to return.

    Returns:
        Issues with code ``TIME_DUPLICATED``.
    """
    issues: list[QualityIssue] = []
    if time_column not in df.columns:
        return issues

    dup_mask = df[time_column].duplicated(keep="first")
    for idx in df.index[dup_mask][:max_examples]:
        issues.append(
            QualityIssue(
                code="TIME_DUPLICATED",
                severity="warning",
                message=f"Duplicate timestamp in column '{time_column}' at row {idx}.",
                column=time_column,
                row_index=_safe_positional_index(df, idx),
                value=str(df.at[idx, time_column]),
            )
        )
    return issues


def check_monotonic_time(
    df: pd.DataFrame,
    time_column: str = "time",
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return warning issues when the time column is not monotonically increasing.

    Args:
        df: DataFrame to inspect.
        time_column: Name of the time column.
        max_examples: Maximum number of issues to return.

    Returns:
        Issues with code ``TIME_NOT_MONOTONIC``.
    """
    issues: list[QualityIssue] = []
    if time_column not in df.columns or len(df) < 2:
        return issues

    parsed = _parse_time_series(df[time_column]).dropna()
    if parsed.is_monotonic_increasing:
        return issues

    # Find the first non-increasing step
    shifted = parsed.shift(1)
    violation_mask = parsed <= shifted
    violation_mask = violation_mask & ~parsed.isna() & ~shifted.isna()
    for idx in parsed.index[violation_mask][:max_examples]:
        issues.append(
            QualityIssue(
                code="TIME_NOT_MONOTONIC",
                severity="warning",
                message=(
                    f"Column '{time_column}' is not monotonically increasing at row {idx}."
                ),
                column=time_column,
                row_index=_safe_positional_index(df, idx),
                value=str(df.at[idx, time_column]),
            )
        )
    return issues


def check_future_times(
    df: pd.DataFrame,
    time_column: str = "time",
    reference_time: pd.Timestamp | None = None,
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return warning issues for timestamps in the future.

    Args:
        df: DataFrame to inspect.
        time_column: Name of the time column.
        reference_time: Upper bound; defaults to ``pd.Timestamp.now()``.
        max_examples: Maximum number of issues to return.

    Returns:
        Issues with code ``TIME_FUTURE_VALUE``.
    """
    issues: list[QualityIssue] = []
    if time_column not in df.columns:
        return issues

    now = reference_time if reference_time is not None else pd.Timestamp.now()
    parsed = _parse_time_series(df[time_column])

    # Strip timezone for comparison if 'now' is tz-naive
    if now.tzinfo is None and parsed.dt.tz is not None:
        parsed = parsed.dt.tz_localize(None)

    future_mask = parsed > now
    for idx in df.index[future_mask][:max_examples]:
        issues.append(
            QualityIssue(
                code="TIME_FUTURE_VALUE",
                severity="warning",
                message=f"Column '{time_column}' has a future timestamp at row {idx}.",
                column=time_column,
                row_index=_safe_positional_index(df, idx),
                value=str(df.at[idx, time_column]),
            )
        )
    return issues


def check_missing_sessions(
    df: pd.DataFrame,
    expected_dates: list[pd.Timestamp] | None,
    time_column: str = "time",
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return info issues for expected trading sessions absent from the DataFrame.

    This is an *optional* check — pass ``expected_dates=None`` to skip it.

    Args:
        df: DataFrame to inspect.
        expected_dates: List of expected trading session dates.  Pass
            ``None`` to disable this check.
        time_column: Name of the time column.
        max_examples: Maximum number of issues to return.

    Returns:
        Issues with code ``TIME_MISSING_SESSIONS``.
    """
    if expected_dates is None or time_column not in df.columns:
        return []

    parsed = _parse_time_series(df[time_column]).dropna().dt.normalize()
    present = set(parsed.dt.date)

    issues: list[QualityIssue] = []
    for ts in expected_dates[:max_examples]:
        if ts.date() not in present:
            issues.append(
                QualityIssue(
                    code="TIME_MISSING_SESSIONS",
                    severity="info",
                    message=f"Expected trading session {ts.date()} is missing.",
                    column=time_column,
                    context={"missing_date": str(ts.date())},
                )
            )
    return issues
