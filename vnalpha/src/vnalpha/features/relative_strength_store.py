from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb


@dataclass(frozen=True, slots=True)
class RelativeStrengthSnapshot:
    symbol: str
    date: str
    benchmark_symbol: str
    horizon_sessions: int
    relative_return: float | None
    source_bar_date: str
    benchmark_bar_date: str | None
    source_row_count: int
    benchmark_row_count: int
    data_status: str
    methodology_version: str
    generated_at: datetime
    lineage_json: str


def save_relative_strength_snapshots(
    conn: duckdb.DuckDBPyConnection,
    snapshots: tuple[RelativeStrengthSnapshot, ...],
) -> None:
    if not snapshots or not _snapshot_table_exists(conn):
        return
    conn.executemany(
        "INSERT INTO relative_strength_snapshot "
        "(symbol, date, benchmark_symbol, horizon_sessions, relative_return, "
        "source_bar_date, benchmark_bar_date, source_row_count, benchmark_row_count, "
        "data_status, methodology_version, generated_at, lineage_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (symbol, date, benchmark_symbol, horizon_sessions) DO UPDATE SET "
        "relative_return = excluded.relative_return, "
        "source_bar_date = excluded.source_bar_date, "
        "benchmark_bar_date = excluded.benchmark_bar_date, "
        "source_row_count = excluded.source_row_count, "
        "benchmark_row_count = excluded.benchmark_row_count, "
        "data_status = excluded.data_status, "
        "methodology_version = excluded.methodology_version, "
        "generated_at = excluded.generated_at, lineage_json = excluded.lineage_json",
        [
            (
                snapshot.symbol,
                snapshot.date,
                snapshot.benchmark_symbol,
                snapshot.horizon_sessions,
                snapshot.relative_return,
                snapshot.source_bar_date,
                snapshot.benchmark_bar_date,
                snapshot.source_row_count,
                snapshot.benchmark_row_count,
                snapshot.data_status,
                snapshot.methodology_version,
                snapshot.generated_at,
                snapshot.lineage_json,
            )
            for snapshot in snapshots
        ],
    )


def _snapshot_table_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'relative_strength_snapshot'",
    ).fetchone()
    return row is not None
