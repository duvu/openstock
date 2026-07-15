from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb

from vnalpha.features.benchmarks import resolve_benchmark


@dataclass(frozen=True, slots=True)
class CanonicalBarLineage:
    provider: str | None
    quality_status: str | None
    ingestion_run_id: str | None


def canonical_bar_lineage(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    bar_date: str,
) -> CanonicalBarLineage:
    row = conn.execute(
        "SELECT selected_provider, quality_status, ingestion_run_id "
        "FROM canonical_ohlcv WHERE symbol = ? AND interval = '1D' "
        "AND CAST(time AS DATE) = ? LIMIT 1",
        [symbol, bar_date],
    ).fetchone()
    if row is None:
        return CanonicalBarLineage(None, None, None)
    return CanonicalBarLineage(
        provider=str(row[0]) if row[0] is not None else None,
        quality_status=str(row[1]) if row[1] is not None else None,
        ingestion_run_id=str(row[2]) if row[2] is not None else None,
    )


def resolve_feature_benchmark(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
    requested_symbol: str | None,
) -> str:
    if not _registry_exists(conn):
        return requested_symbol or "VNINDEX"
    return resolve_benchmark(
        conn,
        symbol,
        date.fromisoformat(target_date),
        requested_symbol,
    ).symbol


def _registry_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'benchmark_definition'",
    ).fetchone()
    return row is not None
