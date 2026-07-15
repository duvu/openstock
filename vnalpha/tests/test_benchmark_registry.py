from __future__ import annotations

from datetime import date

import duckdb
import pytest

from vnalpha.features.benchmarks import BenchmarkSelectionError, resolve_benchmark
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


def test_resolve_benchmark_rejects_inapplicable_explicit_index(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _insert_common_equity(conn, "FPT", "HOSE")

    with pytest.raises(BenchmarkSelectionError, match="not applicable"):
        resolve_benchmark(conn, "FPT", date(2026, 7, 10), requested_symbol="HNXINDEX")


def test_migration_backfills_legacy_vnindex_relative_strength(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    conn.execute(
        """
        INSERT INTO feature_snapshot
            (symbol, date, rs_20d_vs_vnindex, rs_60d_vs_vnindex,
             as_of_bar_date, benchmark_as_of_bar_date, source_row_count,
             benchmark_row_count, feature_data_status, lineage_json)
        VALUES ('FPT', '2026-07-10', 0.12, 0.24, '2026-07-10', '2026-07-10',
                80, 80, 'EXACT_DATE', '{"provider":"fixture"}')
        """
    )

    run_migrations(conn=conn)

    assert conn.execute(
        """
        SELECT benchmark_symbol, horizon_sessions, relative_return,
               source_bar_date, benchmark_bar_date
        FROM relative_strength_snapshot
        WHERE symbol = 'FPT' AND date = '2026-07-10'
        ORDER BY horizon_sessions
        """
    ).fetchall() == [
        ("VNINDEX", 20, 0.12, date(2026, 7, 10), date(2026, 7, 10)),
        ("VNINDEX", 60, 0.24, date(2026, 7, 10), date(2026, 7, 10)),
    ]
