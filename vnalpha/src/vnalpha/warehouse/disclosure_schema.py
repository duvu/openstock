"""Warehouse DDL for official disclosures as verified symbol events (issue #259).

Persists official Vietnamese exchange/company disclosures with trustworthy
publication metadata, then normalizes a small allowlisted event set. Stored
content is treated as untrusted data, never executable instructions.
"""

from __future__ import annotations

# Immutable raw occurrence of a disclosure as seen from an approved source.
DISCLOSURE_RAW_OCCURRENCE_DDL = """
CREATE TABLE IF NOT EXISTS disclosure_raw_occurrence (
    occurrence_id      VARCHAR PRIMARY KEY,
    source_authority   VARCHAR NOT NULL,   -- e.g. HSX, HNX, ISSUER
    source_reference   VARCHAR NOT NULL,   -- opaque source doc reference
    symbol             VARCHAR NOT NULL,
    content_hash       VARCHAR NOT NULL,   -- hash of untrusted raw content
    published_at       DATE NOT NULL,      -- official publication date
    discovered_at      TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    raw_title          VARCHAR,
    raw_payload_json   VARCHAR NOT NULL,   -- stored as untrusted data
    UNIQUE(source_authority, source_reference, content_hash)
)
"""

# Normalized, verified event derived from one or more occurrences.
SYMBOL_EVENT_DDL = """
CREATE TABLE IF NOT EXISTS symbol_event (
    revision_id            VARCHAR PRIMARY KEY,
    event_id               VARCHAR NOT NULL,
    revision_number        INTEGER NOT NULL,
    symbol                 VARCHAR NOT NULL,
    event_type             VARCHAR NOT NULL,   -- allowlisted set only
    verification_status    VARCHAR NOT NULL,   -- VERIFIED, QUARANTINED
    published_at           DATE NOT NULL,      -- when disclosure became public
    event_date             DATE,               -- effective/event date (distinct)
    issuer_reference       VARCHAR,            -- link to issuer/source doc
    source_authority       VARCHAR NOT NULL,
    occurrence_id          VARCHAR NOT NULL,   -- primary source occurrence
    content_hash           VARCHAR NOT NULL,
    revision_hash          VARCHAR NOT NULL,
    canonical_status       VARCHAR NOT NULL,   -- CURRENT, SUPERSEDED
    supersedes_revision_id VARCHAR,
    superseded_by_revision_id VARCHAR,
    title                  VARCHAR,
    contract_version       VARCHAR NOT NULL,
    first_seen_at          TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    diagnostics_json       VARCHAR,
    UNIQUE(event_id, revision_number)
)
"""

SYMBOL_EVENT_IDX = """
CREATE INDEX IF NOT EXISTS idx_symbol_event_symbol_published
ON symbol_event(symbol, published_at)
"""

SYMBOL_EVENT_IDX_TYPE = """
CREATE INDEX IF NOT EXISTS idx_symbol_event_type
ON symbol_event(symbol, event_type, canonical_status)
"""

ALL_DDL_DISCLOSURES = (
    DISCLOSURE_RAW_OCCURRENCE_DDL,
    SYMBOL_EVENT_DDL,
    SYMBOL_EVENT_IDX,
    SYMBOL_EVENT_IDX_TYPE,
)

__all__ = ["ALL_DDL_DISCLOSURES"]
