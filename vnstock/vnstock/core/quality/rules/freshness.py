"""Freshness validation rules for market data DataFrames.

Each function inspects a DataFrame and metadata attributes to determine
whether the data is within an acceptable staleness window.

Returns a list of :class:`~vnstock.core.quality.models.QualityIssue` objects.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from vnstock.core.quality.models import QualityIssue


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _coerce_datetime(value) -> datetime | None:
    """Coerce *value* to a UTC-aware datetime.

    Accepts:
    * ``datetime.datetime`` (tz-aware or tz-naive — naive treated as UTC)
    * ``pd.Timestamp`` (same rules)
    * ISO 8601 string (naive treated as UTC)

    Returns ``None`` on failure so callers can decide how to handle missing
    metadata without raising.
    """
    if value is None:
        return None

    # Already a datetime
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # pd.Timestamp
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).to_pydatetime()
        return value.to_pydatetime().astimezone(timezone.utc)

    # String → parse
    if isinstance(value, str):
        try:
            ts = pd.to_datetime(value, utc=True)
            return ts.to_pydatetime()
        except Exception:
            return None

    return None


def _get_latest_time(df: pd.DataFrame, time_column: str = "time") -> datetime | None:
    """Return the latest parseable timestamp in *time_column*, or None."""
    if time_column not in df.columns or df.empty:
        return None
    series = pd.to_datetime(df[time_column], errors="coerce", utc=True)
    valid = series.dropna()
    if valid.empty:
        return None
    latest = valid.max()
    return latest.to_pydatetime()


def check_stale_price_board(
    df: pd.DataFrame,
    stale_threshold_seconds: int = 30,
    fetched_at: datetime | None = None,
    time_column: str = "time",
) -> list[QualityIssue]:
    """Return issues when a price board snapshot is stale.

    Staleness is evaluated against ``fetched_at`` (the wall-clock time when
    the data was fetched).  Falls back to the latest row timestamp when
    ``fetched_at`` is not provided.

    Args:
        df: DataFrame to inspect.
        stale_threshold_seconds: Maximum acceptable age in seconds.
        fetched_at: UTC datetime when the data was fetched; read from
            ``df.attrs["fetched_at"]`` when not supplied.
        time_column: Name of the time column.

    Returns:
        Issues with code ``FRESHNESS_STALE`` or
        ``FRESHNESS_FETCHED_AT_MISSING``.
    """
    issues: list[QualityIssue] = []
    now = _utc_now()

    raw_ref = fetched_at if fetched_at is not None else df.attrs.get("fetched_at")
    ref = _coerce_datetime(raw_ref)
    if ref is None:
        # Fall back to latest data timestamp
        ref = _get_latest_time(df, time_column)

    if ref is None:
        issues.append(
            QualityIssue(
                code="FRESHNESS_FETCHED_AT_MISSING",
                severity="warning",
                message="No 'fetched_at' metadata and no parseable timestamps found.",
            )
        )
        return issues

    # ref is already UTC-aware after _coerce_datetime / _get_latest_time
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age_seconds = (now - ref).total_seconds()
    if age_seconds > stale_threshold_seconds:
        issues.append(
            QualityIssue(
                code="FRESHNESS_STALE",
                severity="warning",
                message=(
                    f"Price board data is stale: {age_seconds:.0f}s old "
                    f"(threshold: {stale_threshold_seconds}s)."
                ),
                context={
                    "age_seconds": age_seconds,
                    "threshold_seconds": stale_threshold_seconds,
                },
            )
        )
    return issues


def check_stale_intraday(
    df: pd.DataFrame,
    stale_threshold_seconds: int = 60,
    fetched_at: datetime | None = None,
    time_column: str = "time",
) -> list[QualityIssue]:
    """Return issues when an intraday trade feed is stale.

    Args:
        df: DataFrame to inspect.
        stale_threshold_seconds: Maximum acceptable age in seconds.
        fetched_at: UTC datetime when data was fetched; falls back to
            ``df.attrs["fetched_at"]`` then latest row timestamp.
        time_column: Name of the time column.

    Returns:
        Issues with code ``FRESHNESS_STALE`` or
        ``FRESHNESS_FETCHED_AT_MISSING``.
    """
    # Re-use price board logic with different default threshold label
    return check_stale_price_board(
        df,
        stale_threshold_seconds=stale_threshold_seconds,
        fetched_at=fetched_at,
        time_column=time_column,
    )


def check_stale_daily_ohlcv(
    df: pd.DataFrame,
    stale_threshold_hours: int = 36,
    time_column: str = "time",
) -> list[QualityIssue]:
    """Return issues when daily OHLCV data has not been updated recently.

    Uses the latest *data* timestamp rather than a fetch timestamp since
    daily OHLCV is commonly cached for long periods.

    Args:
        df: DataFrame to inspect.
        stale_threshold_hours: Maximum acceptable age in hours.
        time_column: Name of the time column.

    Returns:
        Issues with code ``FRESHNESS_STALE`` or
        ``FRESHNESS_LATEST_TIME_MISSING``.
    """
    issues: list[QualityIssue] = []
    latest = _get_latest_time(df, time_column)

    if latest is None:
        issues.append(
            QualityIssue(
                code="FRESHNESS_LATEST_TIME_MISSING",
                severity="warning",
                message="Could not determine the latest data timestamp for staleness check.",
            )
        )
        return issues

    now = _utc_now()
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    age_hours = (now - latest).total_seconds() / 3600
    if age_hours > stale_threshold_hours:
        issues.append(
            QualityIssue(
                code="FRESHNESS_STALE",
                severity="warning",
                message=(
                    f"Daily OHLCV data is stale: latest timestamp is "
                    f"{age_hours:.1f}h old (threshold: {stale_threshold_hours}h)."
                ),
                context={
                    "age_hours": age_hours,
                    "threshold_hours": stale_threshold_hours,
                    "latest_time": str(latest),
                },
            )
        )
    return issues


def check_latest_time_missing(
    df: pd.DataFrame,
    time_column: str = "time",
) -> list[QualityIssue]:
    """Return a warning when no valid latest timestamp can be extracted.

    Args:
        df: DataFrame to inspect.
        time_column: Name of the time column.

    Returns:
        Issues with code ``FRESHNESS_LATEST_TIME_MISSING``.
    """
    if _get_latest_time(df, time_column) is None:
        return [
            QualityIssue(
                code="FRESHNESS_LATEST_TIME_MISSING",
                severity="warning",
                message=f"No parseable timestamps found in column '{time_column}'.",
                column=time_column,
            )
        ]
    return []
