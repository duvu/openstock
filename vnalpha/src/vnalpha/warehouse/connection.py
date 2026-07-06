"""DuckDB warehouse connection management."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb

from vnalpha.core.config import get_config
from vnalpha.core.logging import get_logger

logger = get_logger("warehouse.connection")

_conn: Optional[duckdb.DuckDBPyConnection] = None


def get_connection(
    path: Optional[Path] = None,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Return the shared warehouse connection.

    For tests, pass a path directly to get an isolated connection.
    """
    global _conn
    if path is not None:
        # Explicit path: always return new connection (useful for tests)
        path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(path), read_only=read_only)
    if _conn is None:
        db_path = get_config().warehouse.path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Opening warehouse at %s", db_path)
        _conn = duckdb.connect(str(db_path), read_only=read_only)
    return _conn


def close_connection() -> None:
    """Close the shared warehouse connection."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def in_memory_connection() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection (for tests)."""
    return duckdb.connect(":memory:")
