from __future__ import annotations

from datetime import date

import duckdb
import pytest

from vnalpha.features.benchmarks import resolve_benchmark
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_common_equity(
    conn: duckdb.DuckDBPyConnection, symbol: str, exchange: str
) -> None:
    conn.execute(
        """
        INSERT INTO symbol_master
            (symbol, exchange, is_active, security_type, lifecycle_status)
        VALUES (?, ?, TRUE, 'COMMON_EQUITY', 'ACTIVE')
        """,
        [symbol, exchange],
    )


def test_resolve_benchmark_selects_exchange_default(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _insert_common_equity(conn, "FPT", "HOSE")
    _insert_common_equity(conn, "HNX", "HNX")
    _insert_common_equity(conn, "MCH", "UPCOM")

    assert resolve_benchmark(conn, "FPT", date(2026, 7, 10)).symbol == "VNINDEX"
    assert resolve_benchmark(conn, "HNX", date(2026, 7, 10)).symbol == "HNXINDEX"
    assert resolve_benchmark(conn, "MCH", date(2026, 7, 10)).symbol == "UPCOMINDEX"
