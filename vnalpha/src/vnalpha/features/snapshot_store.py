from __future__ import annotations

from collections.abc import Mapping

import duckdb

FEATURE_COLUMNS = (
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
)

METADATA_COLUMNS = (
    "as_of_bar_date",
    "benchmark_as_of_bar_date",
    "source_row_count",
    "benchmark_row_count",
    "feature_data_status",
    "feature_build_version",
    "feature_generated_at",
    "lineage_json",
)


def save_feature_snapshot(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date_str: str,
    features: Mapping[str, float | None],
    metadata: Mapping[str, str | int | None] | None = None,
) -> None:
    all_data_columns = (*FEATURE_COLUMNS, *METADATA_COLUMNS)
    columns = ("symbol", "date", *all_data_columns)
    row_metadata = metadata or {}
    values = [symbol, date_str]
    values.extend(features.get(column) for column in FEATURE_COLUMNS)
    values.extend(row_metadata.get(column) for column in METADATA_COLUMNS)
    placeholders = ", ".join("?" for _ in columns)
    update_set = ", ".join(f"{column} = excluded.{column}" for column in all_data_columns)
    conn.execute(
        f"INSERT INTO feature_snapshot ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT (symbol, date) DO UPDATE SET {update_set}",
        values,
    )
