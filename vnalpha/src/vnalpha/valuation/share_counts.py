from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    import duckdb


@dataclass(frozen=True, slots=True)
class ShareCountFact:
    fact_id: str
    revision_number: int
    symbol: str
    effective_date: str
    available_from: str
    shares_outstanding: float
    source_reference: str
    source_authority: str

    def content_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ResolvedShareCount:
    revision_id: str
    shares_outstanding: float
    effective_date: str
    available_from: str
    source_reference: str
    content_hash: str


def upsert_share_count_fact(
    conn: duckdb.DuckDBPyConnection,
    fact: ShareCountFact,
) -> str:
    if fact.shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")
    content_hash = fact.content_hash()
    existing = conn.execute(
        """
        SELECT revision_id, content_hash FROM share_count_fact
        WHERE fact_id = ? AND revision_number = ?
        """,
        [fact.fact_id, fact.revision_number],
    ).fetchone()
    if existing is not None:
        if existing[1] != content_hash:
            raise ValueError("share-count revision is immutable")
        return str(existing[0])

    prior = conn.execute(
        """
        SELECT revision_id FROM share_count_fact
        WHERE fact_id = ? AND canonical_status = 'CURRENT'
        ORDER BY revision_number DESC LIMIT 1
        """,
        [fact.fact_id],
    ).fetchone()
    revision_id = f"shares_{uuid4().hex[:16]}"
    conn.execute(
        """
        INSERT INTO share_count_fact (
            revision_id, fact_id, revision_number, symbol, effective_date,
            available_from, shares_outstanding, source_reference,
            source_authority, content_hash, canonical_status,
            supersedes_revision_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CURRENT', ?)
        """,
        [
            revision_id,
            fact.fact_id,
            fact.revision_number,
            fact.symbol.upper(),
            fact.effective_date,
            fact.available_from,
            fact.shares_outstanding,
            fact.source_reference,
            fact.source_authority,
            content_hash,
            prior[0] if prior else None,
        ],
    )
    if prior is not None:
        conn.execute(
            """
            UPDATE share_count_fact
            SET canonical_status = 'SUPERSEDED', superseded_by_revision_id = ?
            WHERE revision_id = ?
            """,
            [revision_id, prior[0]],
        )
    return revision_id


def resolve_share_count(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: str,
) -> ResolvedShareCount | None:
    """Return the latest share count visible and effective by the as-of date."""
    row = conn.execute(
        """
        SELECT revision_id, shares_outstanding, effective_date, available_from,
               source_reference, content_hash
        FROM share_count_fact
        WHERE symbol = ?
          AND effective_date <= ?
          AND available_from < CAST(? AS DATE) + INTERVAL 1 DAY
        ORDER BY effective_date DESC, available_from DESC, revision_number DESC
        LIMIT 1
        """,
        [symbol.upper(), as_of_date, as_of_date],
    ).fetchone()
    if row is None:
        return None
    return ResolvedShareCount(
        revision_id=str(row[0]),
        shares_outstanding=float(row[1]),
        effective_date=str(row[2]),
        available_from=str(row[3]),
        source_reference=str(row[4]),
        content_hash=str(row[5]),
    )


__all__ = [
    "ResolvedShareCount",
    "ShareCountFact",
    "resolve_share_count",
    "upsert_share_count_fact",
]
