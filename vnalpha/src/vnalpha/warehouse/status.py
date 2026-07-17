from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import duckdb

from vnalpha.warehouse.migrations import run_migrations

_MAX_REPORTED_SCHEMA_GAPS = 20


class WarehouseStatusCode(StrEnum):
    READY = "ready"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    SCHEMA_DRIFT = "schema_drift"
    CHECK_FAILED = "check_failed"


@dataclass(frozen=True, slots=True)
class WarehouseStatus:
    path: str
    code: WarehouseStatusCode
    detail: str
    schema_entries_checked: int = 0
    missing_schema: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.code is WarehouseStatusCode.READY

    def to_dict(self) -> dict[str, bool | int | str | list[str]]:
        return {
            "ready": self.ready,
            "code": self.code.value,
            "path": self.path,
            "detail": self.detail,
            "schema_entries_checked": self.schema_entries_checked,
            "missing_schema": list(self.missing_schema),
        }


def inspect_warehouse(path: Path) -> WarehouseStatus:
    resolved_path = Path(path).expanduser()
    display_path = str(resolved_path)
    if not resolved_path.is_file():
        return WarehouseStatus(
            display_path,
            WarehouseStatusCode.MISSING,
            "Warehouse file does not exist.",
        )

    try:
        with duckdb.connect(str(resolved_path), read_only=True) as connection:
            connection.execute("SELECT 1").fetchone()
            actual_schema = _schema_snapshot(connection)
    except (duckdb.Error, OSError) as exc:
        return WarehouseStatus(
            display_path,
            WarehouseStatusCode.UNREADABLE,
            f"Warehouse could not be opened read-only ({type(exc).__name__}).",
        )

    try:
        with duckdb.connect(":memory:") as expected_connection:
            run_migrations(expected_connection, emit_observability=False)
            expected_schema = _schema_snapshot(expected_connection)
    except duckdb.Error as exc:
        return WarehouseStatus(
            display_path,
            WarehouseStatusCode.CHECK_FAILED,
            f"Migration contract construction failed ({type(exc).__name__}).",
        )

    missing = expected_schema - actual_schema
    if missing:
        missing_schema = tuple(
            _render_schema_entry(entry)
            for entry in sorted(missing)[:_MAX_REPORTED_SCHEMA_GAPS]
        )
        return WarehouseStatus(
            display_path,
            WarehouseStatusCode.SCHEMA_DRIFT,
            "Warehouse schema is older or incompatible with this release.",
            schema_entries_checked=len(expected_schema),
            missing_schema=missing_schema,
        )
    return WarehouseStatus(
        display_path,
        WarehouseStatusCode.READY,
        "Warehouse opens read-only and matches the migration contract.",
        schema_entries_checked=len(expected_schema),
    )


def _schema_snapshot(
    connection: duckdb.DuckDBPyConnection,
) -> frozenset[tuple[str, ...]]:
    column_rows = connection.execute(
        "SELECT table_name, column_name, data_type, is_nullable, "
        "COALESCE(column_default, '') "
        "FROM information_schema.columns "
        "WHERE table_schema = 'main'"
    ).fetchall()
    constraint_rows = connection.execute(
        "SELECT tc.table_name, tc.constraint_type, "
        "COALESCE(string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position), '') "
        "FROM information_schema.table_constraints tc "
        "LEFT JOIN information_schema.key_column_usage kcu "
        "ON tc.constraint_catalog = kcu.constraint_catalog "
        "AND tc.constraint_schema = kcu.constraint_schema "
        "AND tc.constraint_name = kcu.constraint_name "
        "WHERE tc.table_schema = 'main' "
        "AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY') "
        "GROUP BY tc.table_name, tc.constraint_type"
    ).fetchall()
    columns = {("column", *(str(value) for value in row)) for row in column_rows}
    constraints = {
        ("constraint", *(str(value) for value in row)) for row in constraint_rows
    }
    return frozenset(columns | constraints)


def _render_schema_entry(entry: tuple[str, ...]) -> str:
    if entry[0] == "constraint":
        _, table, constraint_type, columns = entry
        return f"{table}:{constraint_type}({columns})"
    _, table, column, data_type, nullable, default = entry
    suffix = f":nullable={nullable}:default={default or '-'}"
    return f"{table}.{column}:{data_type}{suffix}"


__all__ = ["WarehouseStatus", "WarehouseStatusCode", "inspect_warehouse"]
