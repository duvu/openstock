from __future__ import annotations

from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Final, Iterator

import duckdb


@dataclass(frozen=True, slots=True)
class _TransactionState:
    connection: duckdb.DuckDBPyConnection


_ACTIVE_TRANSACTION: Final[ContextVar[_TransactionState | None]] = ContextVar(
    "warehouse_transaction_state", default=None
)


class WarehouseTransactionConflictError(Exception):
    pass


@contextmanager
def warehouse_transaction(
    connection: duckdb.DuckDBPyConnection,
) -> Iterator[duckdb.DuckDBPyConnection]:
    active_transaction = _ACTIVE_TRANSACTION.get()
    if active_transaction is not None and active_transaction.connection is connection:
        try:
            yield connection
        except BaseException:  # noqa: BROAD_EXCEPT_OK
            connection.execute("ROLLBACK")
            connection.execute("BEGIN TRANSACTION")
            raise
        return
    if active_transaction is not None:
        raise WarehouseTransactionConflictError(
            "A nested warehouse transaction requested a different connection."
        )

    connection.execute("BEGIN TRANSACTION")
    transaction = _TransactionState(connection=connection)
    token = _ACTIVE_TRANSACTION.set(transaction)
    transaction_complete = False
    try:
        yield connection
        connection.execute("COMMIT")
        transaction_complete = True
    finally:
        if not transaction_complete:
            with suppress(duckdb.Error):
                connection.execute("ROLLBACK")
        _ACTIVE_TRANSACTION.reset(token)


__all__ = ["WarehouseTransactionConflictError", "warehouse_transaction"]
