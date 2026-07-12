"""DuckDB warehouse connection management."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

import duckdb

from vnalpha.core.config import get_config
from vnalpha.core.logging import get_logger

logger = get_logger("warehouse.connection")

_conn: Optional[duckdb.DuckDBPyConnection] = None


def _to_writable_path(path: Path, read_only: bool) -> Path:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("Opening warehouse connection at %s", path)
        return duckdb.connect(str(path), read_only=read_only)
    except (OSError, duckdb.IOException):
        pass

    fallback_base = Path(tempfile.gettempdir()) / "vnalpha-warehouse"
    fallback_base.mkdir(parents=True, exist_ok=True)
    fallback = fallback_base / path.name
    if not fallback.exists() and path.exists():
        try:
            shutil.copy2(path, fallback)
        except Exception:
            pass
    return duckdb.connect(str(fallback), read_only=read_only)


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
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(path), read_only=read_only)
    db_path = get_config().warehouse.path
    return _to_writable_path(Path(db_path), read_only)


def close_connection() -> None:
    """Close the legacy shared warehouse connection if one was opened."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def in_memory_connection() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection (for tests)."""
    return duckdb.connect(":memory:")
