"""Warehouse migration runner."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.warehouse.connection import get_connection
from vnalpha.warehouse.schema import (
    ALL_DDL,
    ALL_DDL_DEEP_ANALYSIS,
    ALL_DDL_MARKET_CONTEXT,
    ALL_DDL_PHASE6,
    ALL_DDL_PHASE58,
    ALL_DDL_PHASE59,
    ALL_DDL_PHASE510,
    ALL_DDL_SCENARIO_PLAN,
)

logger = get_logger("warehouse.migrations")


def run_migrations(
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    path: Optional[Path] = None,
) -> None:
    """Create all tables if they don't exist.

    Args:
        conn: Use this connection directly (for testing with in-memory).
        path: Create/open a DuckDB file at this path.
    """
    if conn is None:
        conn = get_connection(path=path)
    logger.info("Running warehouse migrations...")
    try:
        from vnalpha.observability.domain import log_migration_start

        log_migration_start("warehouse")
    except Exception:  # noqa: BLE001
        pass
    for ddl in ALL_DDL:
        conn.execute(ddl)
    for ddl in ALL_DDL_PHASE58:
        conn.execute(ddl)
    _migrate_tool_trace_parent_columns(conn)
    for ddl in ALL_DDL_PHASE59:
        conn.execute(ddl)
    for ddl in ALL_DDL_PHASE6:
        conn.execute(ddl)
    for ddl in ALL_DDL_PHASE510:
        conn.execute(ddl)
    for ddl in ALL_DDL_DEEP_ANALYSIS:
        conn.execute(ddl)
    for ddl in ALL_DDL_MARKET_CONTEXT:
        conn.execute(ddl)
    for ddl in ALL_DDL_SCENARIO_PLAN:
        conn.execute(ddl)
    _migrate_feature_snapshot_columns(conn)
    _migrate_rejected_symbol_columns(conn)
    _migrate_candidate_outcome_columns(conn)
    _migrate_aggregate_outcome_columns(conn)
    _migrate_outcome_evaluation_run_columns(conn)
    _migrate_chat_message_visibility_columns(conn)
    logger.info("Warehouse migrations complete.")
    try:
        from vnalpha.observability.domain import log_migration_success

        log_migration_success("warehouse")
    except Exception:  # noqa: BLE001
        pass


def _migrate_tool_trace_parent_columns(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        "ALTER TABLE tool_trace ADD COLUMN IF NOT EXISTS assistant_session_id VARCHAR"
    )
    conn.execute(
        "ALTER TABLE tool_trace ADD COLUMN IF NOT EXISTS trace_parent_type VARCHAR"
    )
    try:
        conn.execute("ALTER TABLE tool_trace ALTER COLUMN session_id DROP NOT NULL")
    except Exception:
        pass


def _migrate_feature_snapshot_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add metadata columns to feature_snapshot for existing databases."""
    cols = [
        ("as_of_bar_date", "DATE"),
        ("benchmark_as_of_bar_date", "DATE"),
        ("source_row_count", "INTEGER"),
        ("benchmark_row_count", "INTEGER"),
        ("feature_data_status", "VARCHAR"),
        ("feature_build_version", "VARCHAR"),
        ("feature_generated_at", "TIMESTAMPTZ"),
        ("lineage_json", "VARCHAR"),
    ]
    for col, col_type in cols:
        conn.execute(
            f"ALTER TABLE feature_snapshot ADD COLUMN IF NOT EXISTS {col} {col_type}"
        )


def _migrate_rejected_symbol_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add lineage columns to rejected_symbol for existing databases."""
    cols = [
        ("ingestion_run_id", "VARCHAR"),
        ("provider", "VARCHAR"),
    ]
    for col, col_type in cols:
        conn.execute(
            f"ALTER TABLE rejected_symbol ADD COLUMN IF NOT EXISTS {col} {col_type}"
        )


def _migrate_candidate_outcome_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add versioning columns to candidate_outcome for existing databases."""
    cols = [
        ("evaluation_run_id", "VARCHAR"),
        ("evaluator_version", "VARCHAR"),
        ("metric_policy_version", "VARCHAR"),
        ("symbol_bar_count", "INTEGER"),
        ("benchmark_bar_count", "INTEGER"),
    ]
    for col, col_type in cols:
        conn.execute(
            f"ALTER TABLE candidate_outcome ADD COLUMN IF NOT EXISTS {col} {col_type}"
        )


def _migrate_aggregate_outcome_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add versioning columns to aggregate outcome tables for existing databases."""
    aggregate_tables = [
        "watchlist_outcome",
        "score_bucket_performance",
        "setup_type_performance",
        "risk_flag_performance",
    ]
    cols = [
        ("evaluation_run_id", "VARCHAR"),
        ("evaluator_version", "VARCHAR"),
        ("metric_policy_version", "VARCHAR"),
    ]
    for table in aggregate_tables:
        for col, col_type in cols:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
            )


def _migrate_outcome_evaluation_run_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """No-op: outcome_evaluation_run was created fresh in Phase 6 DDL."""


def _migrate_chat_message_visibility_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add is_visible and hidden_at columns to chat_message for /clear audit-preserve behavior."""
    conn.execute(
        "ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT TRUE"
    )
    conn.execute(
        "ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS hidden_at TIMESTAMPTZ"
    )
