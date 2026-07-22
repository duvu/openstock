from __future__ import annotations

import hashlib
import json

import duckdb

from vnalpha.ingestion.canonical_validation import CanonicalCandidate
from vnalpha.ingestion.index_provider_policy import (
    is_index_symbol,
    resolve_index_provider_conflict,
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
