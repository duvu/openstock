"""Build feature snapshots for a given date from canonical_ohlcv."""

from __future__ import annotations

import importlib.metadata
import json
from datetime import datetime, timezone
from typing import Optional

import duckdb
import pandas as pd

from vnalpha.core.logging import get_logger
from vnalpha.features.benchmarks import (
    BenchmarkSelectionError,
    registered_benchmark_symbols,
)
from vnalpha.features.build_support import (
    CanonicalBarLineage,
    canonical_bar_lineage,
    resolve_feature_benchmark,
)
from vnalpha.features.completeness import (
    FeatureCompletenessInput,
    evaluate_feature_completeness,
)
from vnalpha.features.price import compute_price_features
from vnalpha.features.relative_strength import compute_relative_strength_features
from vnalpha.features.relative_strength_store import (
    RelativeStrengthSnapshot,
    save_relative_strength_snapshots,
)
from vnalpha.features.snapshot_store import (
    FEATURE_COLUMNS,
    save_feature_snapshot,
)
from vnalpha.features.volatility import compute_volatility_features
from vnalpha.features.volume import compute_volume_features

logger = get_logger("features.build")

try:
    _FEATURE_BUILD_VERSION: str = importlib.metadata.version("vnalpha")
except importlib.metadata.PackageNotFoundError:
    _FEATURE_BUILD_VERSION = "dev"


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
    benchmark_symbol: str = "VNINDEX",
) -> pd.DataFrame:
    """Apply all feature computations to a symbol's OHLCV DataFrame."""
    if df.empty or len(df) < 20:
        return pd.DataFrame()
    df = compute_price_features(df)
    df = compute_volume_features(df)
    df = compute_volatility_features(df)
    if benchmark_df is not None and not benchmark_df.empty:
        df = compute_relative_strength_features(df, benchmark_df, benchmark_symbol)
    else:
        df["rs_20d"] = float("nan")
        df["rs_60d"] = float("nan")
        df["rs_20d_vs_vnindex"] = float("nan")
        df["rs_60d_vs_vnindex"] = float("nan")
    return df


def build_features(
    conn: duckdb.DuckDBPyConnection,
    target_date: str,
    universe: Optional[list[str]] = None,
    benchmark_symbol: str | None = "VNINDEX",
) -> dict[str, int]:
    """Build feature snapshots for all symbols on target_date.

    Returns:
        dict with "built" and "skipped" counts.
    """
    generated_at = datetime.now(timezone.utc)
    try:
        from vnalpha.observability.domain import log_feature_build_start

        log_feature_build_start(target_date)
    except Exception:  # noqa: BLE001
        pass

    if universe is None:
        index_symbols = registered_benchmark_symbols(conn)
        rows = conn.execute("SELECT DISTINCT symbol FROM canonical_ohlcv").fetchall()
        universe = [str(row[0]) for row in rows if str(row[0]) not in index_symbols]

    built = 0
    skipped = 0
    skipped_reasons: list[dict] = []
    for symbol in universe:
        df = load_canonical_ohlcv(conn, symbol, target_date)
        if df.empty:
            skipped += 1
            skipped_reasons.append({"symbol": symbol, "reason": "NO_CANONICAL_DATA"})
            continue
        try:
            selected_benchmark = resolve_feature_benchmark(
                conn, symbol, target_date, benchmark_symbol
            )
        except BenchmarkSelectionError as exc:
            skipped += 1
            skipped_reasons.append({"symbol": symbol, "reason": str(exc)})
            continue
        benchmark_df = load_canonical_ohlcv(conn, selected_benchmark, target_date)
        benchmark_row_count = len(benchmark_df)
        benchmark_as_of = (
            str(benchmark_df.index[-1].date()) if not benchmark_df.empty else None
        )
        features_df = build_features_for_symbol(
            df, benchmark_df if not benchmark_df.empty else None, selected_benchmark
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

        bar_lineage = canonical_bar_lineage(conn, symbol, as_of_bar_date)
        benchmark_lineage = (
            canonical_bar_lineage(conn, selected_benchmark, benchmark_as_of)
            if benchmark_as_of is not None
            else CanonicalBarLineage(None, None, None)
        )
        if bar_lineage.provider is None:
            logger.warning(
                "Feature lineage: provider is missing for symbol=%s bar_date=%s",
                symbol,
                as_of_bar_date,
            )
        if bar_lineage.ingestion_run_id is None:
            logger.debug(
                "Feature lineage: ingestion_run_id is missing for symbol=%s bar_date=%s",
                symbol,
                as_of_bar_date,
            )

        lineage = {
            "provider": bar_lineage.provider,
            "ingestion_run_id": bar_lineage.ingestion_run_id,
            "source_quality_status": bar_lineage.quality_status,
            "as_of_bar_date": as_of_bar_date,
            "benchmark_symbol": selected_benchmark,
            "benchmark_as_of_bar_date": benchmark_as_of,
            "benchmark_provider": benchmark_lineage.provider,
            "benchmark_ingestion_run_id": benchmark_lineage.ingestion_run_id,
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
        completeness = evaluate_feature_completeness(
            FeatureCompletenessInput(
                observed_bar_count=source_row_count,
                exact_date=as_of_bar_date == target_date,
                values={
                    **features,
                    "rs_20d": (
                        None
                        if pd.isna(last_row["rs_20d"])
                        else float(last_row["rs_20d"])
                    ),
                    "rs_60d": (
                        None
                        if pd.isna(last_row["rs_60d"])
                        else float(last_row["rs_60d"])
                    ),
                },
            )
        )
        metadata = {
            "as_of_bar_date": as_of_bar_date,
            "benchmark_as_of_bar_date": benchmark_as_of,
            "source_row_count": source_row_count,
            "benchmark_row_count": benchmark_row_count,
            "feature_data_status": data_status,
            "feature_build_version": _FEATURE_BUILD_VERSION,
            "feature_generated_at": generated_at.isoformat(),
            "lineage_json": json.dumps(lineage),
            "feature_profile": completeness.profile.value,
            "neutral_completeness": completeness.neutral_status.value,
            "relative_strength_completeness": completeness.relative_strength_status.value,
            "required_bar_count": completeness.required_bar_count,
            "observed_bar_count": completeness.observed_bar_count,
            "missing_neutral_fields_json": json.dumps(
                completeness.missing_neutral_fields
            ),
            "missing_relative_strength_fields_json": json.dumps(
                completeness.missing_relative_strength_fields
            ),
            "feature_completeness_rule_version": completeness.rule_version,
        }
        save_feature_snapshot(conn, symbol, target_date, features, metadata)
        save_relative_strength_snapshots(
            conn,
            tuple(
                RelativeStrengthSnapshot(
                    symbol=symbol,
                    date=target_date,
                    benchmark_symbol=selected_benchmark,
                    horizon_sessions=horizon,
                    relative_return=(
                        None if pd.isna(last_row[column]) else float(last_row[column])
                    ),
                    source_bar_date=as_of_bar_date,
                    benchmark_bar_date=benchmark_as_of,
                    source_row_count=source_row_count,
                    benchmark_row_count=benchmark_row_count,
                    data_status=(
                        "SUCCESS"
                        if not pd.isna(last_row[column])
                        else "INCOMPLETE_BENCHMARK"
                    ),
                    methodology_version=_FEATURE_BUILD_VERSION,
                    generated_at=generated_at,
                    lineage_json=json.dumps(lineage),
                )
                for horizon, column in ((20, "rs_20d"), (60, "rs_60d"))
            ),
        )
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
