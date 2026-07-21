from __future__ import annotations

from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import Iterator, assert_never

import duckdb

from vnalpha.core.config import get_config


class WarehouseOpenFailureKind(StrEnum):
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    PERMISSION = "permission"
    SCHEMA = "schema"


class WarehouseFallback(StrEnum):
    DISABLED = "disabled"
    MEMORY = "memory"


class WarehouseOpenError(Exception):
    kind: WarehouseOpenFailureKind
    remediation: str

    def __init__(self, kind: WarehouseOpenFailureKind, remediation: str) -> None:
        self.kind = kind
        self.remediation = remediation
        super().__init__(kind, remediation)

    def __str__(self) -> str:
        return f"Warehouse {self.kind.value}. {self.remediation}"


class WarehouseWriteCoordinatorRequiredError(Exception):
    remediation: str

    def __init__(self) -> None:
        self.remediation = "Use WarehouseWriteCoordinator for every warehouse mutation."
        super().__init__(self.remediation)

    def __str__(self) -> str:
        return self.remediation


def _configured_path(path: Path | str | None) -> Path:
    return Path(path) if path is not None else Path(get_config().warehouse.path)


def warehouse_open_error(exc: BaseException) -> WarehouseOpenError:
    message = str(exc).casefold()
    schema_markers = (
        "not a valid duckdb database",
        "database file is invalid",
        "database version",
        "storage version",
        "corrupt",
        "checksum",
    )
    if isinstance(exc, (duckdb.PermissionException, PermissionError)):
        return WarehouseOpenError(
            WarehouseOpenFailureKind.PERMISSION,
            "Check warehouse and parent-directory permissions.",
        )
    if isinstance(exc, (duckdb.InvalidInputException, duckdb.CatalogException)) or (
        isinstance(exc, duckdb.IOException)
        and any(marker in message for marker in schema_markers)
    ):
        return WarehouseOpenError(
            WarehouseOpenFailureKind.SCHEMA,
            "Run the explicit warehouse migration or restore a compatible backup.",
        )
    if isinstance(exc, BlockingIOError) or "lock" in message:
        return WarehouseOpenError(
            WarehouseOpenFailureKind.BUSY,
            "Wait for the active warehouse writer and retry.",
        )
    return WarehouseOpenError(
        WarehouseOpenFailureKind.UNAVAILABLE,
        "Verify the configured warehouse path and storage availability.",
    )


def _open_connection(path: Path, *, read_only: bool) -> duckdb.DuckDBPyConnection:
    try:
        return duckdb.connect(str(path), read_only=read_only)
    except (duckdb.Error, OSError) as exc:
        raise warehouse_open_error(exc) from exc


def get_connection(
    path: Path | str | None = None,
    read_only: bool = True,
    *,
    fallback: WarehouseFallback = WarehouseFallback.DISABLED,
) -> duckdb.DuckDBPyConnection:
    """Open one fresh read-only connection to the authoritative warehouse."""
    if not read_only:
        raise WarehouseWriteCoordinatorRequiredError
    resolved_path = _configured_path(path)
    try:
        return _open_connection(resolved_path, read_only=True)
    except WarehouseOpenError:
        match fallback:
            case WarehouseFallback.DISABLED:
                raise
            case WarehouseFallback.MEMORY:
                return duckdb.connect(":memory:")
            case unreachable:
                assert_never(unreachable)


@contextmanager
def read_connection(
    path: Path | str | None = None,
    *,
    fallback: WarehouseFallback = WarehouseFallback.DISABLED,
) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = get_connection(path=path, fallback=fallback)
    with connection:
        yield connection


def in_memory_connection() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection (for tests)."""
    return duckdb.connect(":memory:")


__all__ = [
    "WarehouseFallback",
    "WarehouseOpenError",
    "WarehouseOpenFailureKind",
    "WarehouseWriteCoordinatorRequiredError",
    "get_connection",
    "in_memory_connection",
    "read_connection",
    "warehouse_open_error",
]
