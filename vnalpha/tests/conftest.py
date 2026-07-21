"""vnalpha test configuration."""

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import duckdb
import pytest

WarehouseConnectionFactory = Callable[[str], duckdb.DuckDBPyConnection]


@pytest.fixture
def tmp_warehouse(tmp_path):
    """Return a temporary DuckDB warehouse path."""
    return tmp_path / "test_warehouse.duckdb"


@pytest.fixture(scope="session")
def migrated_warehouse_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from vnalpha.warehouse.migrations import run_migrations

    path = tmp_path_factory.mktemp("migrated-warehouse") / "template.duckdb"
    connection = duckdb.connect(str(path))
    try:
        run_migrations(conn=connection, emit_observability=False)
    finally:
        connection.close()
    return path


@pytest.fixture
def migrated_warehouse_connection_factory(
    migrated_warehouse_template: Path, tmp_path: Path
) -> Iterator[WarehouseConnectionFactory]:
    connections: list[duckdb.DuckDBPyConnection] = []

    def create(name: str) -> duckdb.DuckDBPyConnection:
        destination = tmp_path / f"{name}.duckdb"
        if not name or Path(name).name != name or destination.exists():
            raise ValueError(f"invalid isolated warehouse name: {name!r}")
        shutil.copy2(migrated_warehouse_template, destination)
        connection = duckdb.connect(str(destination))
        connections.append(connection)
        return connection

    yield create
    for connection in connections:
        connection.close()


@pytest.fixture
def migrated_warehouse_connection(
    migrated_warehouse_connection_factory: WarehouseConnectionFactory,
) -> Iterator[duckdb.DuckDBPyConnection]:
    yield migrated_warehouse_connection_factory("warehouse")


@pytest.fixture(autouse=True)
def reset_vnalpha_config():
    """Reset config singleton between tests."""
    from vnalpha.core.config import reset_config

    yield
    reset_config()
