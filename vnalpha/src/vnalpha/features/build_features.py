"""Build feature snapshots for a given date from canonical_ohlcv."""

from __future__ import annotations

import importlib.metadata
import json
from datetime import datetime, timezone
from typing import Optional

import duckdb
import pandas as pd

from vnalpha.core.logging import get_logger
from vnalpha.features.price import compute_price_features
from vnalpha.features.relative_strength import compute_relative_strength_features
from vnalpha.features.volatility import compute_volatility_features
from vnalpha.features.volume import compute_volume_features

logger = get_logger("features.build")

try:
    _FEATURE_BUILD_VERSION: str = importlib.metadata.version("vnalpha")
except importlib.metadata.PackageNotFoundError:
    _FEATURE_BUILD_VERSION = "dev"

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

METADATA_COLUMNS = [
    "as_of_bar_date",
    "benchmark_as_of_bar_date",
    "source_row_count",
    "benchmark_row_count",
    "feature_data_status",
    "feature_build_version",
    "feature_generated_at",
    "lineage_json",
]


def _get_bar_lineage(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    bar_date: str,
) -> dict:
    """Query lineage metadata from canonical_ohlcv for a given symbol/bar_date."""
    row = conn.execute(
        """
        SELECT selected_provider, quality_status, ingestion_run_id
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D' AND CAST(time AS DATE) = ?
        LIMIT 1
        """,
        [symbol, bar_date],
    ).fetchone()
    if row is None:
        return {"provider": None, "quality_status": None, "ingestion_run_id": None}
    return {
        "provider": row[0],
        "quality_status": row[1],
        "ingestion_run_id": row[2],
    }


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
    metadata: dict | None = None,
) -> None:
    """Upsert a feature snapshot row."""
    all_data_columns = FEATURE_COLUMNS + METADATA_COLUMNS
    cols = ["symbol", "date"] + all_data_columns
    row_meta = metadata or {}
    values = (
        [symbol, date_str]
        + [features.get(c) for c in FEATURE_COLUMNS]
        + [row_meta.get(c) for c in METADATA_COLUMNS]
    )
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    update_set = ", ".join(f"{c} = excluded.{c}" for c in all_data_columns)
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
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        from vnalpha.observability.domain import log_feature_build_start

        log_feature_build_start(target_date)
    except Exception:  # noqa: BLE001
        pass

    # Load benchmark
    benchmark_df = load_canonical_ohlcv(conn, benchmark_symbol, target_date)
    benchmark_as_of: str | None = None
    benchmark_row_count: int = 0
    if benchmark_df.empty:
        logger.warning(
            "Benchmark '%s' not found in canonical_ohlcv — relative strength features will be NaN. "
            "Run 'vnalpha sync index --symbol %s' to fix this.",
            benchmark_symbol,
            benchmark_symbol,
        )
    else:
        benchmark_row_count = len(benchmark_df)
        bm_row = benchmark_df[benchmark_df.index <= target_date]
        if not bm_row.empty:
            benchmark_as_of = str(bm_row.index[-1].date())

    if universe is None:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM canonical_ohlcv WHERE symbol != ?",
            [benchmark_symbol],
        ).fetchall()
        universe = [r[0] for r in rows]

    built = 0
    skipped = 0
    skipped_reasons: list[dict] = []
    for symbol in universe:
        df = load_canonical_ohlcv(conn, symbol, target_date)
        if df.empty:
            skipped += 1
            skipped_reasons.append({"symbol": symbol, "reason": "NO_CANONICAL_DATA"})
            continue
        features_df = build_features_for_symbol(
            df, benchmark_df if not benchmark_df.empty else None
        )
        if features_df.empty:
            skipped += 1
            skipped_reasons.append(
                {"symbol": symbol, "reason": "INSUFFICIENT_HISTORY", "rows": len(df)}
            )
            continue
        # Get the row for target_date (last available row up to target_date)
        row = features_df[features_df.index <= target_date]
        if row.empty:
            skipped += 1
            skipped_reasons.append({"symbol": symbol, "reason": "NO_ROW_FOR_DATE"})
            continue
        last_row = row.iloc[-1]
        # Record the actual bar date (index) of the last row used
        as_of_bar_date = (
            str(last_row.name.date())
            if hasattr(last_row.name, "date")
            else str(last_row.name)
        )
        source_row_count = len(df)

        if benchmark_df.empty:
            data_status = "MISSING_BENCHMARK"
        elif as_of_bar_date < target_date:
            data_status = "STALE_DATE"
        else:
            data_status = "EXACT_DATE"

        # Fetch lineage from canonical_ohlcv for the actual bar used
        bar_lineage = _get_bar_lineage(conn, symbol, as_of_bar_date)
        if bar_lineage.get("provider") is None:
            logger.warning(
                "Feature lineage: provider is missing for symbol=%s bar_date=%s",
                symbol,
                as_of_bar_date,
            )
        if bar_lineage.get("ingestion_run_id") is None:
            logger.debug(
                "Feature lineage: ingestion_run_id is missing for symbol=%s bar_date=%s",
                symbol,
                as_of_bar_date,
            )

        lineage = {
            "provider": bar_lineage.get("provider"),
            "ingestion_run_id": bar_lineage.get("ingestion_run_id"),
            "source_quality_status": bar_lineage.get("quality_status"),
            "as_of_bar_date": as_of_bar_date,
            "feature_build_version": _FEATURE_BUILD_VERSION,
        }

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
        metadata = {
            "as_of_bar_date": as_of_bar_date,
            "benchmark_as_of_bar_date": benchmark_as_of,
            "source_row_count": source_row_count,
            "benchmark_row_count": benchmark_row_count,
            "feature_data_status": data_status,
            "feature_build_version": _FEATURE_BUILD_VERSION,
            "feature_generated_at": generated_at,
            "lineage_json": json.dumps(lineage),
        }
        save_feature_snapshot(conn, symbol, target_date, features, metadata)
        built += 1

    logger.info("Features built=%d skipped=%d for date=%s", built, skipped, target_date)
    if skipped_reasons:
        logger.debug("Skipped reasons: %s", skipped_reasons)
    try:
        from vnalpha.observability.domain import log_feature_build_success

        log_feature_build_success(target_date, built=built, skipped=skipped)
    except Exception:  # noqa: BLE001
        pass
    return {"built": built, "skipped": skipped}
