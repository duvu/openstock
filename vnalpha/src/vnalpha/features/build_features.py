"""Build feature snapshots for a given date from canonical_ohlcv."""

from __future__ import annotations

from typing import Optional

import duckdb
import pandas as pd

from vnalpha.core.logging import get_logger
from vnalpha.features.price import compute_price_features
from vnalpha.features.relative_strength import compute_relative_strength_features
from vnalpha.features.volatility import compute_volatility_features
from vnalpha.features.volume import compute_volume_features

logger = get_logger("features.build")

FEATURE_COLUMNS = [
    "close",
    "ma20",
    "ma50",
    "ma100",
    "ma20_slope",
    "ma50_slope",
    "volume_ma20",
    "volume_ratio",
    "atr14",
    "return_20d",
    "return_60d",
    "rs_20d_vs_vnindex",
    "rs_60d_vs_vnindex",
    "distance_to_ma20",
    "distance_to_52w_high",
    "base_range_30d",
    "close_strength",
    "volatility_20d",
]


def load_canonical_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Load canonical OHLCV for a symbol up to end_date."""
    query = """
        SELECT time, open, high, low, close, volume
        FROM canonical_ohlcv
        WHERE symbol = ?
        AND interval = '1D'
    """
    params = [symbol]
    if end_date:
        query += " AND time <= ?"
        params.append(end_date)
    query += " ORDER BY time"
    df = conn.execute(query, params).df()
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").sort_index()
    return df


def build_features_for_symbol(
    df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Apply all feature computations to a symbol's OHLCV DataFrame."""
    if df.empty or len(df) < 20:
        return pd.DataFrame()
    df = compute_price_features(df)
    df = compute_volume_features(df)
    df = compute_volatility_features(df)
    if benchmark_df is not None and not benchmark_df.empty:
        df = compute_relative_strength_features(df, benchmark_df)
    else:
        df["rs_20d_vs_vnindex"] = float("nan")
        df["rs_60d_vs_vnindex"] = float("nan")
    return df


def save_feature_snapshot(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date_str: str,
    features: dict,
) -> None:
    """Upsert a feature snapshot row."""
    cols = ["symbol", "date"] + FEATURE_COLUMNS
    values = [symbol, date_str] + [features.get(c) for c in FEATURE_COLUMNS]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    update_set = ", ".join(f"{c} = excluded.{c}" for c in FEATURE_COLUMNS)
    conn.execute(
        f"""
        INSERT INTO feature_snapshot ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (symbol, date) DO UPDATE SET {update_set}
        """,
        values,
    )


def build_features(
    conn: duckdb.DuckDBPyConnection,
    target_date: str,
    universe: Optional[list[str]] = None,
    benchmark_symbol: str = "VNINDEX",
) -> dict[str, int]:
    """Build feature snapshots for all symbols on target_date.

    Returns:
        dict with "built" and "skipped" counts.
    """
    # Load benchmark
    benchmark_df = load_canonical_ohlcv(conn, benchmark_symbol, target_date)

    if universe is None:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM canonical_ohlcv WHERE symbol != ?",
            [benchmark_symbol],
        ).fetchall()
        universe = [r[0] for r in rows]

    built = 0
    skipped = 0
    for symbol in universe:
        df = load_canonical_ohlcv(conn, symbol, target_date)
        if df.empty:
            skipped += 1
            continue
        features_df = build_features_for_symbol(df, benchmark_df)
        if features_df.empty:
            skipped += 1
            continue
        # Get the row for target_date (last available row up to target_date)
        row = features_df[features_df.index <= target_date]
        if row.empty:
            skipped += 1
            continue
        last_row = row.iloc[-1]
        features = {
            c: (None if pd.isna(last_row.get(c, float("nan"))) else float(last_row[c]))
            for c in FEATURE_COLUMNS
            if c != "close"
        }
        features["close"] = (
            float(last_row["close"])
            if "close" in last_row.index and not pd.isna(last_row["close"])
            else None
        )
        save_feature_snapshot(conn, symbol, target_date, features)
        built += 1

    logger.info("Features built=%d skipped=%d for date=%s", built, skipped, target_date)
    return {"built": built, "skipped": skipped}
