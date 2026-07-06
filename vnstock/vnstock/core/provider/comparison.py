"""
Provider data comparison utilities.

These functions compare DataFrames produced by two (or more) providers for the
same dataset, exposing differences in values, coverage, freshness, and schema.
They are intended for data quality monitoring, provider evaluation, and
diagnostics.

None of the functions here make network calls.  They operate on DataFrames
already fetched by provider plugins.

Usage::

    from vnstock.core.provider.comparison import compare_ohlcv, compare_coverage

    diff = compare_ohlcv(df_kbs, df_vci)
    print(diff["max_close_diff_pct"])   # 0.002

    cov = compare_coverage(df_kbs, df_vci, time_col="time")
    print(cov["overlap_rows"])
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_required_columns(df: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{label} is missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )


def _numeric_diff(
    a: pd.Series,
    b: pd.Series,
    tolerance: float | None = None,
) -> dict[str, Any]:
    """Compute absolute and relative difference statistics between two series."""
    diff = (a - b).abs()
    base = b.abs().replace(0, float("nan"))
    rel = diff / base
    result: dict[str, Any] = {
        "max_abs_diff": float(diff.max()) if len(diff) > 0 else None,
        "mean_abs_diff": float(diff.mean()) if len(diff) > 0 else None,
        "max_rel_diff": float(rel.max()) if len(rel) > 0 else None,
        "mean_rel_diff": float(rel.mean()) if len(rel) > 0 else None,
    }
    if tolerance is not None:
        result["within_tolerance"] = bool((diff <= tolerance).all())
        result["tolerance"] = tolerance
    return result


# ---------------------------------------------------------------------------
# OHLCV comparison
# ---------------------------------------------------------------------------

_OHLCV_PRICE_COLS = ["open", "high", "low", "close"]
_OHLCV_VOL_COL = "volume"


def compare_ohlcv(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    label_a: str = "provider_a",
    label_b: str = "provider_b",
    time_col: str = "time",
    price_tolerance: float | None = None,
    volume_tolerance: float | None = None,
) -> dict[str, Any]:
    """Compare two OHLCV DataFrames on the same time index.

    The DataFrames are aligned on *time_col* before comparison.  Rows present
    in only one DataFrame are reported in the coverage section.

    Args:
        df_a: First OHLCV DataFrame.
        df_b: Second OHLCV DataFrame.
        label_a: Human label for *df_a* in result keys.
        label_b: Human label for *df_b* in result keys.
        time_col: Column used for alignment (must exist in both DataFrames).
        price_tolerance: Absolute price tolerance for ``within_tolerance`` flag.
        volume_tolerance: Absolute volume tolerance.

    Returns:
        Dict with per-column difference statistics, alignment report, and
        summary flags.

    Raises:
        ValueError: If required columns are missing.
    """
    _OHLCV_REQUIRED = [time_col] + _OHLCV_PRICE_COLS + [_OHLCV_VOL_COL]
    _check_required_columns(df_a, _OHLCV_REQUIRED, label_a)
    _check_required_columns(df_b, _OHLCV_REQUIRED, label_b)

    # Align on time
    a = df_a.set_index(time_col)
    b = df_b.set_index(time_col)
    shared_index = a.index.intersection(b.index)

    if len(shared_index) == 0:
        return {
            "aligned_rows": 0,
            "only_in_a": len(df_a),
            "only_in_b": len(df_b),
            "price_diffs": {},
            "volume_diff": {},
            "note": "No overlapping timestamps between the two DataFrames.",
        }

    a_aligned = a.loc[shared_index]
    b_aligned = b.loc[shared_index]

    price_diffs = {}
    for col in _OHLCV_PRICE_COLS:
        price_diffs[col] = _numeric_diff(
            a_aligned[col].astype(float),
            b_aligned[col].astype(float),
            tolerance=price_tolerance,
        )

    volume_diff = _numeric_diff(
        a_aligned[_OHLCV_VOL_COL].astype(float),
        b_aligned[_OHLCV_VOL_COL].astype(float),
        tolerance=volume_tolerance,
    )

    max_close_diff_pct = price_diffs["close"].get("max_rel_diff")

    return {
        "aligned_rows": len(shared_index),
        "only_in_a": len(a.index.difference(b.index)),
        "only_in_b": len(b.index.difference(a.index)),
        "price_diffs": price_diffs,
        "volume_diff": volume_diff,
        "max_close_diff_pct": max_close_diff_pct,
        f"{label_a}_rows": len(df_a),
        f"{label_b}_rows": len(df_b),
    }


# ---------------------------------------------------------------------------
# Quote comparison
# ---------------------------------------------------------------------------

_QUOTE_REQUIRED_COLS = ["symbol", "close_price"]


def compare_quote(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    label_a: str = "provider_a",
    label_b: str = "provider_b",
    symbol_col: str = "symbol",
    price_col: str = "close_price",
    price_tolerance: float | None = None,
) -> dict[str, Any]:
    """Compare two quote (price board) DataFrames.

    Aligns on *symbol_col* and compares *price_col* and any other numeric
    columns present in both DataFrames.

    Args:
        df_a: First quote DataFrame.
        df_b: Second quote DataFrame.
        label_a: Human label for *df_a*.
        label_b: Human label for *df_b*.
        symbol_col: Column used for alignment.
        price_col: Primary price column to compare.
        price_tolerance: Absolute tolerance for ``within_tolerance`` flag.

    Returns:
        Dict with per-column statistics and symbol coverage.

    Raises:
        ValueError: If required columns are missing.
    """
    for col in [symbol_col]:
        if col not in df_a.columns:
            raise ValueError(f"{label_a} is missing required column: {col}")
        if col not in df_b.columns:
            raise ValueError(f"{label_b} is missing required column: {col}")

    a = df_a.set_index(symbol_col)
    b = df_b.set_index(symbol_col)
    shared = a.index.intersection(b.index)

    result: dict[str, Any] = {
        "aligned_symbols": len(shared),
        "only_in_a": list(a.index.difference(b.index)),
        "only_in_b": list(b.index.difference(a.index)),
        "column_diffs": {},
    }

    if len(shared) == 0:
        result["note"] = "No overlapping symbols."
        return result

    a_al = a.loc[shared]
    b_al = b.loc[shared]

    # Compare price_col if present in both
    if price_col in a_al.columns and price_col in b_al.columns:
        result["column_diffs"][price_col] = _numeric_diff(
            a_al[price_col].astype(float),
            b_al[price_col].astype(float),
            tolerance=price_tolerance,
        )

    # Compare any other shared numeric columns
    shared_cols = set(a_al.columns) & set(b_al.columns) - {price_col}
    for col in sorted(shared_cols):
        try:
            result["column_diffs"][col] = _numeric_diff(
                a_al[col].astype(float),
                b_al[col].astype(float),
            )
        except (TypeError, ValueError):
            pass  # Skip non-numeric columns

    return result


# ---------------------------------------------------------------------------
# Intraday shape comparison
# ---------------------------------------------------------------------------


def compare_intraday_shape(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    label_a: str = "provider_a",
    label_b: str = "provider_b",
    time_col: str = "time",
) -> dict[str, Any]:
    """Compare the structural shape of two intraday trades DataFrames.

    Does not compare values — only row count, column set, time range, and
    whether the time column is monotonically increasing.

    Args:
        df_a: First intraday DataFrame.
        df_b: Second intraday DataFrame.
        label_a: Human label for *df_a*.
        label_b: Human label for *df_b*.
        time_col: Name of the timestamp column.

    Returns:
        Dict with shape comparison fields.
    """
    result: dict[str, Any] = {
        f"{label_a}_rows": len(df_a),
        f"{label_b}_rows": len(df_b),
        f"{label_a}_columns": sorted(df_a.columns.tolist()),
        f"{label_b}_columns": sorted(df_b.columns.tolist()),
        "column_diff": {
            f"only_in_{label_a}": sorted(set(df_a.columns) - set(df_b.columns)),
            f"only_in_{label_b}": sorted(set(df_b.columns) - set(df_a.columns)),
        },
    }

    for label, df in [(label_a, df_a), (label_b, df_b)]:
        if time_col in df.columns:
            try:
                times = pd.to_datetime(df[time_col], errors="coerce")
                result[f"{label}_time_range"] = {
                    "min": str(times.min()),
                    "max": str(times.max()),
                }
                result[f"{label}_time_monotonic"] = bool(times.is_monotonic_increasing)
            except Exception:  # noqa: BLE001
                result[f"{label}_time_range"] = None

    return result


# ---------------------------------------------------------------------------
# Coverage comparison
# ---------------------------------------------------------------------------


def compare_coverage(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    label_a: str = "provider_a",
    label_b: str = "provider_b",
    time_col: str = "time",
) -> dict[str, Any]:
    """Compare temporal coverage of two DataFrames.

    Reports the date range, row count, and overlap statistics.

    Args:
        df_a: First DataFrame.
        df_b: Second DataFrame.
        label_a: Human label for *df_a*.
        label_b: Human label for *df_b*.
        time_col: Column containing timestamps.

    Returns:
        Dict with coverage statistics.

    Raises:
        ValueError: If *time_col* is missing from either DataFrame.
    """
    _check_required_columns(df_a, [time_col], label_a)
    _check_required_columns(df_b, [time_col], label_b)

    times_a = pd.to_datetime(df_a[time_col], errors="coerce").dropna()
    times_b = pd.to_datetime(df_b[time_col], errors="coerce").dropna()

    result: dict[str, Any] = {
        f"{label_a}_rows": len(df_a),
        f"{label_b}_rows": len(df_b),
        f"{label_a}_start": str(times_a.min()) if len(times_a) > 0 else None,
        f"{label_a}_end": str(times_a.max()) if len(times_a) > 0 else None,
        f"{label_b}_start": str(times_b.min()) if len(times_b) > 0 else None,
        f"{label_b}_end": str(times_b.max()) if len(times_b) > 0 else None,
    }

    if len(times_a) > 0 and len(times_b) > 0:
        overlap_start = max(times_a.min(), times_b.min())
        overlap_end = min(times_a.max(), times_b.max())
        if overlap_start <= overlap_end:
            overlap_a = int(
                ((times_a >= overlap_start) & (times_a <= overlap_end)).sum()
            )
            overlap_b = int(
                ((times_b >= overlap_start) & (times_b <= overlap_end)).sum()
            )
            result["overlap_start"] = str(overlap_start)
            result["overlap_end"] = str(overlap_end)
            result["overlap_rows"] = min(overlap_a, overlap_b)
        else:
            result["overlap_start"] = None
            result["overlap_end"] = None
            result["overlap_rows"] = 0

    return result


# ---------------------------------------------------------------------------
# Freshness comparison
# ---------------------------------------------------------------------------


def compare_freshness(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    label_a: str = "provider_a",
    label_b: str = "provider_b",
    time_col: str = "time",
) -> dict[str, Any]:
    """Compare data freshness (recency of the most recent record) between
    two DataFrames.

    Args:
        df_a: First DataFrame.
        df_b: Second DataFrame.
        label_a: Human label for *df_a*.
        label_b: Human label for *df_b*.
        time_col: Column containing timestamps.

    Returns:
        Dict comparing the latest timestamps and flagging which provider is
        fresher.

    Raises:
        ValueError: If *time_col* is missing from either DataFrame.
    """
    _check_required_columns(df_a, [time_col], label_a)
    _check_required_columns(df_b, [time_col], label_b)

    times_a = pd.to_datetime(df_a[time_col], errors="coerce").dropna()
    times_b = pd.to_datetime(df_b[time_col], errors="coerce").dropna()

    latest_a = times_a.max() if len(times_a) > 0 else None
    latest_b = times_b.max() if len(times_b) > 0 else None

    result: dict[str, Any] = {
        f"{label_a}_latest": str(latest_a) if latest_a is not None else None,
        f"{label_b}_latest": str(latest_b) if latest_b is not None else None,
        "fresher_provider": None,
        "staleness_delta_seconds": None,
    }

    if latest_a is not None and latest_b is not None:
        delta = (latest_a - latest_b).total_seconds()
        result["staleness_delta_seconds"] = delta
        if delta > 0:
            result["fresher_provider"] = label_a
        elif delta < 0:
            result["fresher_provider"] = label_b
        else:
            result["fresher_provider"] = "equal"

    return result
