"""Warehouse DDL for publication-aware share facts and valuation snapshots."""

from __future__ import annotations

SHARE_COUNT_FACT_DDL = """
CREATE TABLE IF NOT EXISTS share_count_fact (
    revision_id VARCHAR PRIMARY KEY,
    fact_id VARCHAR NOT NULL,
    revision_number INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    effective_date DATE NOT NULL,
    available_from TIMESTAMPTZ NOT NULL,
    shares_outstanding DOUBLE NOT NULL,
    source_reference VARCHAR NOT NULL,
    source_authority VARCHAR NOT NULL,
    content_hash VARCHAR NOT NULL,
    canonical_status VARCHAR NOT NULL,
    supersedes_revision_id VARCHAR,
    superseded_by_revision_id VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(fact_id, revision_number)
)
"""

VALUATION_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS valuation_snapshot (
    snapshot_id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    price DOUBLE,
    price_basis VARCHAR NOT NULL,
    price_date DATE,
    eps DOUBLE,
    book_value_per_share DOUBLE,
    shares_outstanding DOUBLE,
    fundamental_period VARCHAR,
    fundamental_published_at DATE,
    sector_code VARCHAR,
    taxonomy_version VARCHAR,
    pe_ratio DOUBLE,
    earnings_yield DOUBLE,
    pb_ratio DOUBLE,
    book_yield DOUBLE,
    historical_pe_percentile DOUBLE,
    sector_pe_percentile DOUBLE,
    caveats_json VARCHAR NOT NULL,
    lineage_json VARCHAR NOT NULL,
    contract_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(symbol, as_of_date, price_basis)
)
"""

VALUATION_SNAPSHOT_REVISION_DDL = """
CREATE TABLE IF NOT EXISTS valuation_snapshot_revision (
    revision_id VARCHAR PRIMARY KEY,
    snapshot_key VARCHAR NOT NULL,
    revision_number INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    price_basis VARCHAR NOT NULL,
    content_hash VARCHAR NOT NULL,
    canonical_status VARCHAR NOT NULL,
    supersedes_revision_id VARCHAR,
    superseded_by_revision_id VARCHAR,
    payload_json VARCHAR NOT NULL,
    lineage_json VARCHAR NOT NULL,
    caveats_json VARCHAR NOT NULL,
    contract_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(snapshot_key, revision_number)
)
"""

VALUATION_SNAPSHOT_IDX = """
CREATE INDEX IF NOT EXISTS idx_valuation_snapshot_symbol_date
ON valuation_snapshot(symbol, as_of_date)
"""

VALUATION_SNAPSHOT_IDX_SECTOR = """
CREATE INDEX IF NOT EXISTS idx_valuation_snapshot_sector
ON valuation_snapshot(sector_code, as_of_date)
"""

VALUATION_REVISION_IDX = """
CREATE INDEX IF NOT EXISTS idx_valuation_revision_key_status
ON valuation_snapshot_revision(snapshot_key, canonical_status, revision_number)
"""

SHARE_COUNT_IDX = """
CREATE INDEX IF NOT EXISTS idx_share_count_symbol_available
ON share_count_fact(symbol, available_from, effective_date)
"""

ALL_DDL_VALUATION = (
    SHARE_COUNT_FACT_DDL,
    VALUATION_SNAPSHOT_DDL,
    VALUATION_SNAPSHOT_REVISION_DDL,
    VALUATION_SNAPSHOT_IDX,
    VALUATION_SNAPSHOT_IDX_SECTOR,
    VALUATION_REVISION_IDX,
    SHARE_COUNT_IDX,
)

__all__ = ["ALL_DDL_VALUATION"]
