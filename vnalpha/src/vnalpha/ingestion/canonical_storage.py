"""DuckDB persistence operations for canonical OHLCV promotion."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import duckdb

from vnalpha.ingestion.canonical_validation import (
    CANONICAL_VALIDATION_VERSION,
    CanonicalCandidate,
    CanonicalValidationRule,
)
from vnalpha.ingestion.index_provider_policy import (
    is_index_symbol,
    resolve_index_provider_conflict,
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
        WHERE interval = ? {symbol_filter}
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
        "price_basis": candidate.price_basis,
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


def _passing_bar_candidates(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT provider, open, high, low, close, volume, ingestion_run_id,
               CASE
                   WHEN UPPER(TRIM(COALESCE(provider, ''))) = 'FIINQUANTX'
                   THEN price_basis
                   ELSE COALESCE(price_basis, 'RAW_UNADJUSTED')
               END AS resolved_basis
        FROM market_ohlcv_raw
        WHERE symbol = ?
          AND UPPER(interval) = UPPER(?)
          AND CASE WHEN UPPER(interval) = '1D'
                   THEN CAST(CAST(time AS DATE) AS TIMESTAMP)
                   ELSE time END = ?
          AND LOWER(TRIM(COALESCE(quality_status, ''))) IN ('pass', 'success')
        ORDER BY LOWER(provider), ingestion_run_id
        """,
        [candidate.symbol, candidate.interval, candidate.timestamp],
    ).fetchall()
    return [
        {
            "provider": str(row[0] or "").lower(),
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
            "ingestion_run_id": row[6],
            "price_basis": row[7],
        }
        for row in rows
        if row[0]
    ]


def persist_selection_audit(
    conn: duckdb.DuckDBPyConnection,
    candidate: CanonicalCandidate,
) -> str | None:
    """Persist the evidence and policy used for a conflicting index selection."""
    if not is_index_symbol(candidate.symbol) or not candidate.provider:
        return None
    observations = _passing_bar_candidates(conn, candidate)
    providers = tuple(dict.fromkeys(str(item["provider"]) for item in observations))
    values = {
        (
            item["open"],
            item["high"],
            item["low"],
            item["close"],
            item["volume"],
        )
        for item in observations
    }
    if len(providers) < 2 or len(values) < 2:
        return None
    resolution = resolve_index_provider_conflict(candidate.symbol, providers)
    if resolution is None:
        return None
    if candidate.provider.strip().lower() != resolution.selected_provider:
        return None

    payload = {
        "symbol": candidate.symbol,
        "time": candidate.timestamp.isoformat(),
        "interval": candidate.interval,
        "observations": observations,
        "selected_provider": resolution.selected_provider,
        "rejected_providers": list(resolution.rejected_providers),
        "policy_version": resolution.policy_version,
        "policy_family": resolution.policy_family,
        "policy_rationale": resolution.rationale,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    content_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    audit_id = f"canonical-selection-{content_hash[:24]}"
    conn.execute(
        """
        INSERT INTO canonical_selection_audit (
            audit_id, symbol, time, interval, candidate_providers_json,
            selected_provider, rejected_providers_json, candidate_values_json,
            policy_version, policy_family, policy_rationale,
            evidence_refs_json, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (audit_id) DO NOTHING
        """,
        [
            audit_id,
            candidate.symbol,
            candidate.timestamp,
            candidate.interval,
            json.dumps(list(providers)),
            resolution.selected_provider,
            json.dumps(list(resolution.rejected_providers)),
            json.dumps(observations, sort_keys=True, default=str),
            resolution.policy_version,
            resolution.policy_family,
            resolution.rationale,
            json.dumps(
                [
                    f"market_ohlcv_raw:{item['ingestion_run_id']}:{item['provider']}"
                    for item in observations
                ]
            ),
            content_hash,
        ],
    )
    return audit_id


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
