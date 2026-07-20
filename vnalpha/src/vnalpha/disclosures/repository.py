"""Persistence + normalization + as-of queries for disclosures (issue #259)."""

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
    conn: duckdb.DuckDBPyConnection, occurrence: DisclosureOccurrence
) -> str:
    """Persist a raw disclosure occurrence, deduplicating identical copies.

    Duplicate copies (same authority + reference + content hash) resolve to the
    existing occurrence without losing the original; the raw payload is stored
    as untrusted data. Returns the occurrence_id.
    """
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
            occurrence.symbol,
            content_hash,
            occurrence.published_at,
            occurrence.raw_title,
            json.dumps(occurrence.raw_payload, sort_keys=True),
        ],
    )
    conn.commit()
    return occurrence_id


def normalize_event(
    conn: duckdb.DuckDBPyConnection,
    occurrence: DisclosureOccurrence,
    *,
    event_type: EventType,
    event_id: str,
    event_date: str | None = None,
) -> NormalizedEvent:
    """Normalize an occurrence into a symbol event.

    Only occurrences from an approved official source become ``VERIFIED``;
    anything else is stored ``QUARANTINED``. A revised disclosure for the same
    ``event_id`` supersedes the prior revision immutably rather than
    overwriting it. ``published_at`` (disclosure) and ``event_date`` (effective)
    are kept distinct.
    """
    occurrence_id = ingest_occurrence(conn, occurrence)
    content_hash = occurrence_content_hash(occurrence)

    verification = (
        VerificationStatus.VERIFIED
        if is_approved_source(occurrence.source_authority)
        else VerificationStatus.QUARANTINED
    )

    prior = conn.execute(
        """
        SELECT revision_id, revision_number FROM symbol_event
        WHERE event_id = ? AND canonical_status = 'CURRENT'
        ORDER BY revision_number DESC LIMIT 1
        """,
        [event_id],
    ).fetchone()
    revision_number = (prior[1] + 1) if prior else 1
    revision_id = f"evt_{uuid4().hex[:16]}"
    revision_hash = content_hash

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
            occurrence.symbol,
            event_type.value,
            verification.value,
            occurrence.published_at,
            event_date,
            occurrence.source_reference,
            occurrence.source_authority,
            occurrence_id,
            content_hash,
            revision_hash,
            prior[0] if prior else None,
            occurrence.raw_title,
            DISCLOSURES_CONTRACT_VERSION,
            json.dumps({}),
        ],
    )
    if prior is not None:
        conn.execute(
            """
            UPDATE symbol_event
            SET canonical_status = 'SUPERSEDED', superseded_by_revision_id = ?
            WHERE revision_id = ?
            """,
            [revision_id, prior[0]],
        )
    conn.commit()
    return NormalizedEvent(
        revision_id=revision_id,
        event_id=event_id,
        symbol=occurrence.symbol,
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
    """Return current symbol events published on or before the as-of date.

    Future disclosures (``published_at > as_of_date``) can never leak into a
    historical read. Only ``CURRENT`` revisions are returned so superseded
    evidence does not reappear.
    """
    query = """
        SELECT event_id, event_type, verification_status, published_at,
               event_date, issuer_reference, source_authority, title
        FROM symbol_event
        WHERE symbol = ? AND canonical_status = 'CURRENT'
          AND published_at <= ?
    """
    params: list[object] = [symbol, as_of_date]
    if verified_only:
        query += " AND verification_status = 'VERIFIED'"
    query += " ORDER BY published_at DESC, event_type"
    rows = conn.execute(query, params).fetchall()
    return [
        {
            "event_id": r[0],
            "event_type": r[1],
            "verification_status": r[2],
            "published_at": str(r[3]),
            "event_date": str(r[4]) if r[4] is not None else None,
            "issuer_reference": r[5],
            "source_authority": r[6],
            "title": r[7],
        }
        for r in rows
    ]


__all__ = [
    "NormalizedEvent",
    "as_of_events",
    "ingest_occurrence",
    "normalize_event",
]
