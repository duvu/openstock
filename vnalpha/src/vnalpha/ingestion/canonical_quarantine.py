from __future__ import annotations

import json

import duckdb

from vnalpha.ingestion.canonical_validation import (
    CANONICAL_VALIDATION_VERSION,
    CanonicalCandidate,
    CanonicalValidationRule,
)


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
