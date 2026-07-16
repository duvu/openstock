"""Warehouse migration runner."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.warehouse.connection import get_connection
from vnalpha.warehouse.corporate_action_schema import ALL_DDL_CORPORATE_ACTIONS
from vnalpha.warehouse.ingestion_migrations import migrate_ingestion_run_outcome_columns
from vnalpha.warehouse.research_answer_schema import ALL_DDL_RESEARCH_ANSWER_AUDIT
from vnalpha.warehouse.research_models_schema import ALL_DDL_RESEARCH_MODELS
from vnalpha.warehouse.sandbox_migrations import (
    SANDBOX_DDL,
    migrate_sandbox_contract_columns,
)
from vnalpha.warehouse.schema import (
    ALL_DDL,
    ALL_DDL_MARKET_CONTEXT,
    ALL_DDL_PHASE6,
    ALL_DDL_PHASE58,
    ALL_DDL_PHASE59,
    ALL_DDL_PHASE510,
    ALL_DDL_RESEARCH_AUTOMATION,
)
from vnalpha.warehouse.symbol_memory_schema import ALL_DDL_SYMBOL_MEMORY

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
    for ddl in ALL_DDL_CORPORATE_ACTIONS:
        conn.execute(ddl)
    migrate_ingestion_run_outcome_columns(conn)
    for ddl in SANDBOX_DDL:
        conn.execute(ddl)
    migrate_sandbox_contract_columns(conn)
    for ddl in ALL_DDL_PHASE58:
        conn.execute(ddl)
    _migrate_tool_trace_parent_columns(conn)
    for ddl in ALL_DDL_PHASE59:
        conn.execute(ddl)
    for ddl in ALL_DDL_RESEARCH_ANSWER_AUDIT:
        conn.execute(ddl)
    for ddl in ALL_DDL_RESEARCH_MODELS:
        conn.execute(ddl)
    for ddl in ALL_DDL_SYMBOL_MEMORY:
        conn.execute(ddl)
    _migrate_symbol_memory_columns(conn)
    _migrate_research_answer_audit_columns(conn)
    _migrate_research_artifact_columns(conn)
    for ddl in ALL_DDL_PHASE6:
        conn.execute(ddl)
    for ddl in ALL_DDL_RESEARCH_AUTOMATION:
        conn.execute(ddl)
    for ddl in ALL_DDL_PHASE510:
        conn.execute(ddl)
    for ddl in ALL_DDL_MARKET_CONTEXT:
        conn.execute(ddl)
    _migrate_market_context_columns(conn)
    _migrate_symbol_master_lifecycle_columns(conn)
    _migrate_feature_snapshot_columns(conn)
    _seed_benchmark_definitions(conn)
    _backfill_legacy_relative_strength(conn)
    _migrate_rejected_symbol_columns(conn)
    _migrate_candidate_outcome_columns(conn)
    _migrate_aggregate_outcome_columns(conn)
    _migrate_outcome_evaluation_run_columns(conn)
    _migrate_chat_message_visibility_columns(conn)
    _migrate_assistant_prompt_columns(conn)
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


def _migrate_assistant_prompt_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add prompt projection columns to databases created before hardening."""

    for column, column_type in (
        ("prompt_text", "VARCHAR"),
        ("prompt_summary", "VARCHAR"),
        ("prompt_hash", "VARCHAR"),
        ("prompt_chars", "INTEGER"),
        ("workspace_context_ref", "VARCHAR"),
        ("chat_context_ref", "VARCHAR"),
        ("raw_stored", "BOOLEAN DEFAULT FALSE"),
    ):
        conn.execute(
            f"ALTER TABLE assistant_session ADD COLUMN IF NOT EXISTS {column} {column_type}"
        )


def _migrate_symbol_memory_columns(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        "ALTER TABLE memory_claim ADD COLUMN IF NOT EXISTS source_published_at DATE"
    )


def _migrate_symbol_master_lifecycle_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add current lifecycle and taxonomy projection fields to legacy warehouses."""

    for column, column_type in (
        ("security_type", "VARCHAR"),
        ("listing_date", "DATE"),
        ("delisting_date", "DATE"),
        ("lifecycle_status", "VARCHAR"),
        ("sector_code", "VARCHAR"),
        ("sector_name", "VARCHAR"),
        ("industry_code", "VARCHAR"),
        ("industry_name", "VARCHAR"),
        ("taxonomy_name", "VARCHAR"),
        ("taxonomy_version", "VARCHAR"),
        ("classification_source", "VARCHAR"),
        ("classification_effective_from", "TIMESTAMPTZ"),
        ("last_seen_source_snapshot_id", "VARCHAR"),
    ):
        conn.execute(
            f"ALTER TABLE symbol_master ADD COLUMN IF NOT EXISTS {column} {column_type}"
        )


def _migrate_research_answer_audit_columns(conn: duckdb.DuckDBPyConnection) -> None:
    for column, column_type in (
        ("research_session_id", "VARCHAR"),
        ("missing_data_json", "VARCHAR"),
    ):
        conn.execute(
            f"ALTER TABLE research_answer_audit ADD COLUMN IF NOT EXISTS {column} {column_type}"
        )


def _migrate_research_artifact_columns(conn: duckdb.DuckDBPyConnection) -> None:
    if not _table_exists(conn, "research_artifact"):
        return
    conn.execute(
        "ALTER TABLE research_artifact ADD COLUMN IF NOT EXISTS lifecycle_state VARCHAR"
    )
    conn.execute(
        "ALTER TABLE research_artifact ADD COLUMN IF NOT EXISTS lineage_path VARCHAR"
    )
    conn.execute(
        "UPDATE research_artifact SET lineage_path = '' WHERE lineage_path IS NULL"
    )
    if "status" in _table_columns(conn, "research_artifact"):
        conn.execute(
            "UPDATE research_artifact "
            "SET lifecycle_state = CASE status "
            "WHEN 'created' THEN 'RUN' "
            "WHEN 'running' THEN 'OBSERVE' "
            "WHEN 'succeeded' THEN 'PROMOTE_READY' "
            "WHEN 'validated' THEN 'VALIDATE' "
            "WHEN 'promoted' THEN 'PROMOTED' "
            "WHEN 'rejected' THEN 'REJECTED' "
            "WHEN 'failed' THEN 'FAILED' "
            "ELSE 'RUN' "
            "END "
            "WHERE lifecycle_state IS NULL"
        )
    else:
        conn.execute(
            "UPDATE research_artifact "
            "SET lifecycle_state = 'RUN' "
            "WHERE lifecycle_state IS NULL"
        )


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = ? AND table_schema = 'main'",
            [table],
        ).fetchone()
        is not None
    )


def _table_columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ?",
            [table],
        ).fetchall()
    }


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
        ("feature_profile", "VARCHAR"),
        ("neutral_completeness", "VARCHAR"),
        ("relative_strength_completeness", "VARCHAR"),
        ("required_bar_count", "INTEGER"),
        ("observed_bar_count", "INTEGER"),
        ("missing_neutral_fields_json", "VARCHAR"),
        ("missing_relative_strength_fields_json", "VARCHAR"),
        ("feature_completeness_rule_version", "VARCHAR"),
    ]
    for col, col_type in cols:
        conn.execute(
            f"ALTER TABLE feature_snapshot ADD COLUMN IF NOT EXISTS {col} {col_type}"
        )
    conn.execute(
        "UPDATE feature_snapshot SET feature_profile = 'LEGACY_UNKNOWN' "
        "WHERE feature_profile IS NULL"
    )
    conn.execute(
        "UPDATE feature_snapshot SET neutral_completeness = 'LEGACY_UNKNOWN' "
        "WHERE neutral_completeness IS NULL"
    )
    conn.execute(
        "UPDATE feature_snapshot SET relative_strength_completeness = 'LEGACY_UNKNOWN' "
        "WHERE relative_strength_completeness IS NULL"
    )


def _seed_benchmark_definitions(conn: duckdb.DuckDBPyConnection) -> None:
    conn.executemany(
        "INSERT INTO benchmark_definition "
        "(symbol, benchmark_type, exchange, universe, role, source, methodology_version) "
        "VALUES (?, ?, ?, ?, ?, 'openstock', 'v1') ON CONFLICT (symbol) DO NOTHING",
        [
            ("VNINDEX", "MARKET", None, None, "DEFAULT"),
            ("VN30", "SIZE", "HOSE", "VN30", "SECONDARY"),
            ("HNXINDEX", "MARKET", "HNX", None, "DEFAULT"),
            ("UPCOMINDEX", "MARKET", "UPCOM", None, "DEFAULT"),
        ],
    )


def _backfill_legacy_relative_strength(conn: duckdb.DuckDBPyConnection) -> None:
    for horizon, column in ((20, "rs_20d_vs_vnindex"), (60, "rs_60d_vs_vnindex")):
        conn.execute(
            "INSERT INTO relative_strength_snapshot "
            "(symbol, date, benchmark_symbol, horizon_sessions, relative_return, "
            "source_bar_date, benchmark_bar_date, source_row_count, benchmark_row_count, "
            "data_status, methodology_version, generated_at, lineage_json) "
            "SELECT symbol, date, 'VNINDEX', ?, "
            f"{column}, as_of_bar_date, benchmark_as_of_bar_date, source_row_count, "
            "benchmark_row_count, COALESCE(feature_data_status, 'LEGACY'), "
            "COALESCE(feature_build_version, 'legacy-vnindex'), feature_generated_at, lineage_json "
            f"FROM feature_snapshot WHERE {column} IS NOT NULL "
            "ON CONFLICT (symbol, date, benchmark_symbol, horizon_sessions) DO NOTHING",
            [horizon],
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


def _migrate_market_context_columns(conn: duckdb.DuckDBPyConnection) -> None:
    market_columns = {
        row[0]
        for row in conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'market_regime_snapshot'
            """
        ).fetchall()
    }
    if "ma20_slope" in market_columns and "ma50_slope" not in market_columns:
        conn.execute(
            "ALTER TABLE market_regime_snapshot RENAME COLUMN ma20_slope TO ma50_slope"
        )
    if (
        "breadth_feature_count" in market_columns
        and "breadth_active_count" not in market_columns
    ):
        conn.execute(
            "ALTER TABLE market_regime_snapshot RENAME COLUMN breadth_eligible_count TO breadth_active_count"
        )
        conn.execute(
            "ALTER TABLE market_regime_snapshot ADD COLUMN breadth_eligible_count INTEGER"
        )
        conn.execute(
            "ALTER TABLE market_regime_snapshot ADD COLUMN breadth_excluded_count INTEGER"
        )
        conn.execute(
            "ALTER TABLE market_regime_snapshot ADD COLUMN breadth_coverage DOUBLE"
        )
        conn.execute(
            """
            UPDATE market_regime_snapshot
            SET breadth_eligible_count = breadth_feature_count,
                breadth_excluded_count = breadth_active_count - breadth_feature_count,
                breadth_coverage = breadth_feature_count::DOUBLE / breadth_active_count
            WHERE breadth_active_count > 0
            """
        )
    for column, column_type in (
        ("breadth_active_count", "INTEGER"),
        ("breadth_eligible_count", "INTEGER"),
        ("breadth_excluded_count", "INTEGER"),
        ("breadth_coverage", "DOUBLE"),
    ):
        conn.execute(
            f"ALTER TABLE market_regime_snapshot ADD COLUMN IF NOT EXISTS {column} {column_type}"
        )
    for column in ("return20", "return60"):
        if column not in market_columns:
            conn.execute(
                f"ALTER TABLE market_regime_snapshot ADD COLUMN {column} DOUBLE"
            )
        else:
            conn.execute(
                f"ALTER TABLE market_regime_snapshot ALTER COLUMN {column} DROP NOT NULL"
            )
    sector_columns = {
        row[0]: row[1]
        for row in conn.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'sector_strength_snapshot'
            """
        ).fetchall()
    }
    leadership_count_type = sector_columns.get("leadership_count")
    if leadership_count_type is None:
        conn.execute(
            "ALTER TABLE sector_strength_snapshot ADD COLUMN leadership_count INTEGER"
        )
    elif leadership_count_type.upper() != "INTEGER":
        conn.execute(
            """
            ALTER TABLE sector_strength_snapshot
            ALTER COLUMN leadership_count SET DATA TYPE INTEGER
            USING CASE
                WHEN TRY_CAST(leadership_count AS DOUBLE) = FLOOR(TRY_CAST(leadership_count AS DOUBLE))
                THEN TRY_CAST(leadership_count AS INTEGER)
                ELSE NULL
            END
            """
        )
