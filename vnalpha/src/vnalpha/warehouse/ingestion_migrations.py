from __future__ import annotations

import duckdb


def migrate_ingestion_run_outcome_columns(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    for column, column_type in (
        ("requested_count", "INTEGER DEFAULT 0"),
        ("success_count", "INTEGER DEFAULT 0"),
        ("empty_count", "INTEGER DEFAULT 0"),
        ("failed_count", "INTEGER DEFAULT 0"),
        ("invalid_count", "INTEGER DEFAULT 0"),
        ("skipped_count", "INTEGER DEFAULT 0"),
        ("failed_symbols_json", "VARCHAR"),
        ("symbol_results_json", "VARCHAR"),
        ("quality_report_json", "VARCHAR"),
        ("diagnostics_json", "VARCHAR"),
        ("terminal_reason", "VARCHAR"),
        ("correlation_id", "VARCHAR"),
    ):
        conn.execute(
            f"ALTER TABLE ingestion_run ADD COLUMN IF NOT EXISTS {column} {column_type}"
        )
