"""DuckDB persistence operations for canonical OHLCV promotion."""

from __future__ import annotations

import json
from datetime import datetime

import duckdb

from vnalpha.ingestion.canonical_validation import (
    CANONICAL_VALIDATION_VERSION,
    CanonicalCandidate,
    CanonicalValidationRule,
)

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
    str,
]


def load_ranked_candidates(
    conn: duckdb.DuckDBPyConnection,
    symbol: str | None,
    interval: str,
) -> tuple[CanonicalCandidate, ...]:
    """Load raw candidates in the established deterministic preference order."""

    symbol_filter = "AND symbol = ?" if symbol is not None else ""
    params = [interval] + ([symbol] if symbol is not None else [])
    rows = conn.execute(
        f"""
        SELECT
            symbol, time, interval, open, high, low, close, volume, provider,
            quality_status, ingestion_run_id
        FROM market_ohlcv_raw
        WHERE interval = ? {symbol_filter}
        ORDER BY
            symbol,
            time,
            interval,
            CASE
                WHEN LOWER(TRIM(COALESCE(quality_status, ''))) = 'pass' THEN 0
                ELSE 1
            END,
            CASE
                WHEN fetched_at IS NOT NULL THEN fetched_at
                ELSE TIMESTAMP '1970-01-01'
            END DESC,
            ingestion_run_id DESC
        """,
        params,
    ).fetchall()
    candidates: list[CanonicalCandidate] = []
    for row in rows:
        raw_row: RawCandidateRow = row
        candidates.append(CanonicalCandidate(*raw_row))
    return tuple(candidates)


def persist_quarantine(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
    rules: tuple[CanonicalValidationRule, ...],
) -> None:
    """Persist legacy and provider/run-keyed evidence for an invalid candidate."""

    invalid_values = {
        "open": candidate.open,
        "high": candidate.high,
        "low": candidate.low,
        "close": candidate.close,
        "volume": candidate.volume,
    }
    details = {
        "rule_ids": [rule.value for rule in rules],
        "validation_version": CANONICAL_VALIDATION_VERSION,
        "timestamp": candidate.timestamp.isoformat(),
        "interval": candidate.interval,
        **invalid_values,
    }
    conn.execute(
        """
        INSERT INTO rejected_symbol
            (symbol, date, stage, reason, details_json, provider, ingestion_run_id)
        VALUES (?, CAST(? AS DATE), 'canonical', 'INVALID_OHLCV', ?, ?, ?)
        ON CONFLICT (symbol, date, stage) DO UPDATE SET
            reason = excluded.reason,
            details_json = excluded.details_json,
            provider = excluded.provider,
            ingestion_run_id = excluded.ingestion_run_id
        """,
        [
            candidate.symbol,
            candidate.timestamp,
            json.dumps(details, sort_keys=True),
            candidate.provider,
            candidate.ingestion_run_id,
        ],
    )
    conn.execute(
        """
        INSERT INTO ohlcv_quarantine
            (ingestion_run_id, symbol, time, interval, provider, rule_ids_json,
             validation_version, invalid_values_json, first_detected_at,
             last_detected_at, resolution_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp, current_timestamp,
                NULL)
        ON CONFLICT (ingestion_run_id, symbol, time, interval, provider)
        DO UPDATE SET
            rule_ids_json = excluded.rule_ids_json,
            validation_version = excluded.validation_version,
            invalid_values_json = excluded.invalid_values_json,
            last_detected_at = excluded.last_detected_at,
            resolution_ref = NULL
        """,
        [
            candidate.ingestion_run_id,
            candidate.symbol,
            candidate.timestamp,
            candidate.interval,
            candidate.provider or "",
            json.dumps([rule.value for rule in rules]),
            CANONICAL_VALIDATION_VERSION,
            json.dumps(invalid_values, sort_keys=True),
        ],
    )


def upsert_canonical(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
) -> None:
    """Persist one validated raw candidate as the canonical bar."""

    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume,
             selected_provider, quality_status, ingestion_run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (symbol, time, interval) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            selected_provider = excluded.selected_provider,
            quality_status = excluded.quality_status,
            ingestion_run_id = excluded.ingestion_run_id
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
            candidate.quality_status,
            candidate.ingestion_run_id,
        ],
    )


def delete_canonical_bar(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
) -> None:
    """Remove a formerly canonical bar when its selected candidate is invalid."""

    conn.execute(
        """
        DELETE FROM canonical_ohlcv
        WHERE symbol = ? AND time = ? AND interval = ?
        """,
        [candidate.symbol, candidate.timestamp, candidate.interval],
    )


def resolve_quarantines(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
) -> None:
    """Record which valid canonical observation resolved quarantined evidence."""

    resolution_ref = (
        f"canonical:{candidate.ingestion_run_id}:{candidate.provider or ''}"
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
    """Count canonical bars inside the caller's requested scope."""

    count_filter = "AND symbol = ?" if symbol is not None else ""
    count_params = [interval] + ([symbol] if symbol is not None else [])
    row = conn.execute(
        f"SELECT COUNT(*) FROM canonical_ohlcv WHERE interval = ? {count_filter}",
        count_params,
    ).fetchone()
    return int(row[0]) if row is not None else 0
