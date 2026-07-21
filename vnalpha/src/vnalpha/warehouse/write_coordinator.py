from __future__ import annotations

import fcntl
import hashlib
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterator

import duckdb

from vnalpha.warehouse.connection import (
    _configured_path,
    _open_connection,
    warehouse_open_error,
)
from vnalpha.warehouse.transaction import warehouse_transaction


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
            with warehouse_transaction(active_write.connection):
                yield active_write.connection
            return
        lock_path = _warehouse_lock_path(warehouse_path)
        try:
            warehouse_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if warehouse_path.parent.stat().st_mode & 0o002:
                raise PermissionError("Warehouse parent must not be world-writable.")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(lock_path.parent, 0o700)
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
            )
        except OSError as exc:
            raise warehouse_open_error(exc) from exc
        locked = False
        operation_failed = False
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                locked = True
            except OSError as exc:
                raise warehouse_open_error(exc) from exc
            connection = _open_connection(warehouse_path, read_only=False)
            try:
                os.chmod(warehouse_path, 0o600)
            except OSError as exc:
                connection.close()
                raise warehouse_open_error(exc) from exc
            token = _ACTIVE_WRITE.set(_ActiveWrite(warehouse_path, connection))
            try:
                with warehouse_transaction(connection):
                    yield connection
            finally:
                operation_failed = sys.exc_info()[0] is not None
                _ACTIVE_WRITE.reset(token)
                try:
                    connection.close()
                except (duckdb.Error, OSError) as exc:
                    if not operation_failed:
                        raise warehouse_open_error(exc) from exc
        finally:
            operation_failed = operation_failed or sys.exc_info()[0] is not None
            cleanup_error: OSError | None = None
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError as exc:
                    cleanup_error = exc
            try:
                os.close(descriptor)
            except OSError as exc:
                cleanup_error = cleanup_error or exc
            if cleanup_error is not None and not operation_failed:
                raise warehouse_open_error(cleanup_error) from cleanup_error


class WarehouseWritePathConflictError(Exception):
    active_path: Path
    requested_path: Path

    def __init__(self, *, active_path: Path, requested_path: Path) -> None:
        self.active_path = active_path
        self.requested_path = requested_path
        super().__init__(active_path, requested_path)

    def __str__(self) -> str:
        return "A nested warehouse write requested a different database path."


def _warehouse_lock_path(warehouse_path: Path) -> Path:
    identity = hashlib.sha256(os.fsencode(str(warehouse_path))).hexdigest()
    return warehouse_path.parent / ".vnalpha-locks" / f"{identity}.lock"


__all__ = ["WarehouseWriteCoordinator", "WarehouseWritePathConflictError"]
