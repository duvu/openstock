from __future__ import annotations

import json
from dataclasses import dataclass

import duckdb


@dataclass(frozen=True, slots=True)
class RelativeStrengthEvidence:
    available: bool
    benchmark_symbol: str
    benchmark_bar_date: str | None
    benchmark_row_count: int | None


def get_relative_strength_evidence(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
) -> RelativeStrengthEvidence:
    lineage_row = conn.execute(
        "SELECT lineage_json FROM feature_snapshot WHERE symbol = ? AND date = ?",
        [symbol, target_date],
    ).fetchone()
    benchmark_symbol = _benchmark_symbol(lineage_row[0] if lineage_row else None)
    if not _snapshot_table_exists(conn):
        return RelativeStrengthEvidence(True, benchmark_symbol, None, None)
    row = conn.execute(
        "SELECT count(*), max(benchmark_bar_date)::VARCHAR, max(benchmark_row_count) "
        "FROM relative_strength_snapshot WHERE symbol = ? AND date = ? "
        "AND benchmark_symbol = ? AND data_status = 'SUCCESS' "
        "AND horizon_sessions IN (20, 60)",
        [symbol, target_date, benchmark_symbol],
    ).fetchone()
    count = int(row[0]) if row is not None else 0
    return RelativeStrengthEvidence(
        available=count == 2,
        benchmark_symbol=benchmark_symbol,
        benchmark_bar_date=str(row[1]) if row and row[1] is not None else None,
        benchmark_row_count=int(row[2]) if row and row[2] is not None else None,
    )


def _benchmark_symbol(lineage_json: str | None) -> str:
    if lineage_json is None:
        return "VNINDEX"
    try:
        decoded = json.loads(lineage_json)
    except json.JSONDecodeError:
        return "VNINDEX"
    if not isinstance(decoded, dict):
        return "VNINDEX"
    value = decoded.get("benchmark_symbol")
    return str(value) if value else "VNINDEX"


def _snapshot_table_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'relative_strength_snapshot'",
    ).fetchone()
    return row is not None
