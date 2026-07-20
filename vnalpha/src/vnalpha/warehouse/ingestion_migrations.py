from __future__ import annotations

import duckdb


_CANONICAL_SELECTION_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS canonical_selection_audit (
    audit_id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    time TIMESTAMP NOT NULL,
    interval VARCHAR NOT NULL,
    candidate_providers_json VARCHAR NOT NULL,
    selected_provider VARCHAR NOT NULL,
    rejected_providers_json VARCHAR NOT NULL,
    candidate_values_json VARCHAR NOT NULL,
    policy_version VARCHAR NOT NULL,
    policy_rationale VARCHAR NOT NULL,
    evidence_refs_json VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(symbol, time, interval, policy_version)
)
"""


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
    conn.execute(_CANONICAL_SELECTION_AUDIT_DDL)
    conn.execute(
        "ALTER TABLE canonical_ohlcv "
        "ADD COLUMN IF NOT EXISTS selection_audit_id VARCHAR"
    )
