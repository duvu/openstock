"""Persistence, normalization and historical as-of queries for disclosures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from vnalpha.disclosures.models import (
    DISCLOSURES_CONTRACT_VERSION,
    DisclosureOccurrence,
    EventType,
    VerificationStatus,
    is_approved_source,
    occurrence_content_hash,
)

if TYPE_CHECKING:
    import duckdb


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    revision_id: str
    event_id: str
    symbol: str
    event_type: str
    verification_status: str
    published_at: str
    event_date: str | None
    canonical_status: str


def ingest_occurrence(
    conn: duckdb.DuckDBPyConnection,
    occurrence: DisclosureOccurrence,
) -> str:
    """Persist one immutable source occurrence; exact copies are idempotent."""
    content_hash = occurrence_content_hash(occurrence)
    existing = conn.execute(
        """
        SELECT occurrence_id FROM disclosure_raw_occurrence
        WHERE source_authority = ? AND source_reference = ? AND content_hash = ?
        """,
        [occurrence.source_authority, occurrence.source_reference, content_hash],
    ).fetchone()
    if existing is not None:
        return str(existing[0])

    occurrence_id = f"disc_{uuid4().hex[:16]}"
    conn.execute(
        """
        INSERT INTO disclosure_raw_occurrence (
            occurrence_id, source_authority, source_reference, symbol,
            content_hash, published_at, raw_title, raw_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            occurrence_id,
            occurrence.source_authority,
            occurrence.source_reference,
            occurrence.symbol.upper(),
            content_hash,
            occurrence.published_at,
            occurrence.raw_title,
            json.dumps(occurrence.raw_payload, sort_keys=True),
        ],
    )
    return occurrence_id


def normalize_event(
    conn: duckdb.DuckDBPyConnection,
    occurrence: DisclosureOccurrence,
    *,
    event_type: EventType,
    event_id: str,
    event_date: str | None = None,
) -> NormalizedEvent:
    """Normalize one allowlisted event with immutable superseding revisions."""
    occurrence_id = ingest_occurrence(conn, occurrence)
    content_hash = occurrence_content_hash(occurrence)
    verification = (
        VerificationStatus.VERIFIED
        if is_approved_source(occurrence.source_authority)
        else VerificationStatus.QUARANTINED
    )

    current = conn.execute(
        """
        SELECT revision_id, revision_number, content_hash, event_type,
               verification_status, published_at, event_date
        FROM symbol_event
        WHERE event_id = ? AND canonical_status = 'CURRENT'
        ORDER BY revision_number DESC LIMIT 1
        """,
        [event_id],
    ).fetchone()
    if (
        current is not None
        and current[2] == content_hash
        and current[3] == event_type.value
        and current[4] == verification.value
        and str(current[5]) == occurrence.published_at
        and (str(current[6]) if current[6] is not None else None) == event_date
    ):
        return NormalizedEvent(
            revision_id=str(current[0]),
            event_id=event_id,
            symbol=occurrence.symbol.upper(),
            event_type=event_type.value,
            verification_status=verification.value,
            published_at=occurrence.published_at,
            event_date=event_date,
            canonical_status="CURRENT",
        )

    revision_number = int(current[1]) + 1 if current else 1
    revision_id = f"evt_{uuid4().hex[:16]}"
    conn.execute(
        """
        INSERT INTO symbol_event (
            revision_id, event_id, revision_number, symbol, event_type,
            verification_status, published_at, event_date, issuer_reference,
            source_authority, occurrence_id, content_hash, revision_hash,
            canonical_status, supersedes_revision_id, title, contract_version,
            diagnostics_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CURRENT', ?, ?, ?, ?)
        """,
        [
            revision_id,
            event_id,
            revision_number,
            occurrence.symbol.upper(),
            event_type.value,
            verification.value,
            occurrence.published_at,
            event_date,
            occurrence.source_reference,
            occurrence.source_authority,
            occurrence_id,
            content_hash,
            content_hash,
            current[0] if current else None,
            occurrence.raw_title,
            DISCLOSURES_CONTRACT_VERSION,
            json.dumps({"content_is_untrusted": True}),
        ],
    )
    if current is not None:
        conn.execute(
            """
            UPDATE symbol_event
            SET canonical_status = 'SUPERSEDED', superseded_by_revision_id = ?
            WHERE revision_id = ?
            """,
            [revision_id, current[0]],
        )
    return NormalizedEvent(
        revision_id=revision_id,
        event_id=event_id,
        symbol=occurrence.symbol.upper(),
        event_type=event_type.value,
        verification_status=verification.value,
        published_at=occurrence.published_at,
        event_date=event_date,
        canonical_status="CURRENT",
    )


def as_of_events(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: str,
    *,
    verified_only: bool = True,
) -> list[dict[str, object]]:
    """Return the latest revision visible for each event by ``as_of_date``.

    A revision published later may supersede the current view, but it cannot
    erase the earlier revision from a historical read.
    """
    verification_filter = (
        "AND verification_status = 'VERIFIED'" if verified_only else ""
    )
    rows = conn.execute(
        f"""
        WITH visible AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY event_id
                       ORDER BY published_at DESC, revision_number DESC
                   ) AS rn
            FROM symbol_event
            WHERE symbol = ? AND published_at <= ?
              {verification_filter}
        )
        SELECT revision_id, event_id, event_type, verification_status,
               published_at, event_date, issuer_reference, source_authority,
               title, content_hash, revision_number
        FROM visible
        WHERE rn = 1
        ORDER BY published_at DESC, event_type, event_id
        """,
        [symbol.upper(), as_of_date],
    ).fetchall()
    return [
        {
            "revision_id": str(row[0]),
            "event_id": row[1],
            "event_type": row[2],
            "verification_status": row[3],
            "published_at": str(row[4]),
            "event_date": str(row[5]) if row[5] is not None else None,
            "issuer_reference": row[6],
            "source_authority": row[7],
            "title": row[8],
            "content_hash": row[9],
            "revision_number": row[10],
        }
        for row in rows
    ]


__all__ = [
    "NormalizedEvent",
    "as_of_events",
    "ingest_occurrence",
    "normalize_event",
]
