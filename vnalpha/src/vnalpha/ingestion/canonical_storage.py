"""DuckDB persistence operations for canonical OHLCV promotion."""

from __future__ import annotations

from datetime import datetime

import duckdb

from vnalpha.ingestion.canonical_selection_audit import persist_selection_audit
from vnalpha.ingestion.canonical_validation import CanonicalCandidate

RawCandidateRow = tuple[
    str,
    datetime,
    str,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    str | None,
    str | None,
    str | None,
    str,
]


def load_ranked_candidates(
    conn: duckdb.DuckDBPyConnection,
    symbol: str | None,
    interval: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> tuple[CanonicalCandidate, ...]:
    """Load raw candidates in the established deterministic preference order."""
    if (start is None) != (end is None):
        raise ValueError("canonical promotion range requires both start and end")
    symbol_filter = "AND symbol = ?" if symbol is not None else ""
    date_filter = "AND CAST(time AS DATE) BETWEEN ? AND ?" if start else ""
    params = [interval] + ([symbol] if symbol is not None else [])
    if start is not None and end is not None:
        params.extend((start, end))
    rows = conn.execute(
        f"""
        SELECT
            symbol,
            CASE WHEN interval = '1D'
                 THEN CAST(CAST(time AS DATE) AS TIMESTAMP)
                 ELSE time END AS time,
            interval,
            open, high, low, close, volume, provider,
            CASE
                WHEN UPPER(TRIM(COALESCE(provider, ''))) = 'FIINQUANTX'
                THEN price_basis
                ELSE COALESCE(price_basis, 'RAW_UNADJUSTED')
            END AS price_basis,
            quality_status, ingestion_run_id
        FROM market_ohlcv_raw
        WHERE interval = ? {symbol_filter} {date_filter}
        ORDER BY
            symbol,
            time,
            interval,
            CASE WHEN price_basis = 'RAW_UNADJUSTED' THEN 0 ELSE 1 END,
            CASE
                WHEN LOWER(TRIM(COALESCE(quality_status, ''))) IN ('pass', 'success')
                THEN 0 ELSE 1
            END,
            CASE
                WHEN fetched_at IS NOT NULL THEN fetched_at
                ELSE TIMESTAMP '1970-01-01'
            END DESC,
            ingestion_run_id DESC
        """,
        params,
    ).fetchall()
    return tuple(CanonicalCandidate(*row) for row in rows)


def upsert_canonical(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
) -> None:
    """Persist one validated candidate with optional selection provenance."""
    selection_audit_id = persist_selection_audit(conn, candidate)
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume,
             selected_provider, price_basis, quality_status, ingestion_run_id,
             selection_audit_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (symbol, time, interval) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            selected_provider = excluded.selected_provider,
            price_basis = excluded.price_basis,
            quality_status = excluded.quality_status,
            ingestion_run_id = excluded.ingestion_run_id,
            selection_audit_id = excluded.selection_audit_id
        """,
        [
            candidate.symbol,
            candidate.timestamp,
            candidate.interval,
            candidate.open,
            candidate.high,
            candidate.low,
            candidate.close,
            candidate.volume,
            candidate.provider,
            candidate.price_basis,
            candidate.quality_status,
            candidate.ingestion_run_id,
            selection_audit_id,
        ],
    )


def delete_canonical_bar(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
) -> None:
    conn.execute(
        "DELETE FROM canonical_ohlcv WHERE symbol = ? AND time = ? AND interval = ?",
        [candidate.symbol, candidate.timestamp, candidate.interval],
    )


def delete_stray_intraday_canonical_rows(
    conn: duckdb.DuckDBPyConnection,
    symbol: str | None,
    interval: str,
) -> int:
    symbol_filter = "AND symbol = ?" if symbol is not None else ""
    params: list[str] = [interval] + ([symbol] if symbol is not None else [])
    result = conn.execute(
        f"""
        DELETE FROM canonical_ohlcv
        WHERE interval = ? {symbol_filter}
          AND time != CAST(CAST(time AS DATE) AS TIMESTAMP)
        """,
        params,
    )
    return result.fetchone()[0]


def resolve_quarantines(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
) -> None:
    row = conn.execute(
        """
        SELECT selection_audit_id FROM canonical_ohlcv
        WHERE symbol = ? AND time = ? AND interval = ?
        """,
        [candidate.symbol, candidate.timestamp, candidate.interval],
    ).fetchone()
    resolution_ref = (
        f"canonical-selection:{row[0]}"
        if row and row[0]
        else f"canonical:{candidate.ingestion_run_id}:{candidate.provider or ''}"
    )
    conn.execute(
        """
        UPDATE ohlcv_quarantine
        SET resolution_ref = ?
        WHERE symbol = ? AND time = ? AND interval = ?
        """,
        [
            resolution_ref,
            candidate.symbol,
            candidate.timestamp,
            candidate.interval,
        ],
    )


def count_canonical_rows(
    conn: duckdb.DuckDBPyConnection,
    symbol: str | None,
    interval: str,
) -> int:
    count_filter = "AND symbol = ?" if symbol is not None else ""
    count_params = [interval] + ([symbol] if symbol is not None else [])
    row = conn.execute(
        f"SELECT COUNT(*) FROM canonical_ohlcv WHERE interval = ? {count_filter}",
        count_params,
    ).fetchone()
    return int(row[0]) if row is not None else 0
