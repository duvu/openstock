"""Warehouse migration runner."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.warehouse.connection import get_connection
from vnalpha.warehouse.schema import ALL_DDL

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
    for ddl in ALL_DDL:
        conn.execute(ddl)
    logger.info("Warehouse migrations complete.")
