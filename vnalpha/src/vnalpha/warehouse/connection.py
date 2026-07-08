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
    """Return a warehouse connection.

    Always returns a fresh connection so that callers that call .close() after
    use (e.g. ChatController, TUI screens) do not invalidate a shared
    singleton.  Pass an explicit *path* to connect to a non-default warehouse
    (useful for tests).
    """
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(path), read_only=read_only)
    db_path = get_config().warehouse.path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.debug("Opening warehouse connection at %s", db_path)
    return duckdb.connect(str(db_path), read_only=read_only)


def close_connection() -> None:
    """Close the legacy shared warehouse connection if one was opened."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def in_memory_connection() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection (for tests)."""
    return duckdb.connect(":memory:")
