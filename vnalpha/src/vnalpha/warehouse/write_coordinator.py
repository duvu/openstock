from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterator

import duckdb

from vnalpha.warehouse.connection import _configured_path, _open_connection


@dataclass(frozen=True, slots=True)
class _ActiveWrite:
    path: Path
    connection: duckdb.DuckDBPyConnection


_ACTIVE_WRITE: Final[ContextVar[_ActiveWrite | None]] = ContextVar(
    "warehouse_active_write", default=None
)


@dataclass(frozen=True, slots=True)
class WarehouseWriteCoordinator:
    """Own the global lock, writable connection, and transaction lifecycle."""

    path: Path | str | None = None
    lock_path: Path | str | None = None

    @contextmanager
    def transaction(self) -> Iterator[duckdb.DuckDBPyConnection]:
        warehouse_path = _configured_path(self.path).expanduser().resolve()
        active_write = _ACTIVE_WRITE.get()
        if active_write is not None:
            if active_write.path != warehouse_path:
                raise WarehouseWritePathConflictError(
                    active_path=active_write.path,
                    requested_path=warehouse_path,
                )
            yield active_write.connection
            return
        lock_path = (
            Path(self.lock_path)
            if self.lock_path is not None
            else Path(f"{warehouse_path}.writer.lock")
        )
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            warehouse_path.parent.mkdir(parents=True, exist_ok=True)
            connection = _open_connection(warehouse_path, read_only=False)
            try:
                connection.execute("BEGIN TRANSACTION")
                token = _ACTIVE_WRITE.set(_ActiveWrite(warehouse_path, connection))
                transaction_complete = False
                try:
                    yield connection
                    connection.execute("COMMIT")
                    transaction_complete = True
                finally:
                    if transaction_complete:
                        connection.close()
                    else:
                        with suppress(duckdb.Error):
                            connection.execute("ROLLBACK")
                        with suppress(duckdb.Error):
                            connection.close()
                    _ACTIVE_WRITE.reset(token)
            except duckdb.Error:
                with suppress(duckdb.Error):
                    connection.close()
                raise
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


class WarehouseWritePathConflictError(Exception):
    active_path: Path
    requested_path: Path

    def __init__(self, *, active_path: Path, requested_path: Path) -> None:
        self.active_path = active_path
        self.requested_path = requested_path
        super().__init__(active_path, requested_path)

    def __str__(self) -> str:
        return "A nested warehouse write requested a different database path."


__all__ = ["WarehouseWriteCoordinator", "WarehouseWritePathConflictError"]
