"""Warehouse DDL for derived valuation snapshots (issue #258).

Reproducible valuation snapshots derived from canonical price, publication-aware
fundamentals (#257), explicit share data and point-in-time sector membership.
Every snapshot declares its price / fundamental / share / taxonomy lineage.
"""

from __future__ import annotations

VALUATION_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS valuation_snapshot (
    snapshot_id            VARCHAR PRIMARY KEY,
    symbol                 VARCHAR NOT NULL,
    as_of_date             DATE NOT NULL,
    price                  DOUBLE,
    price_basis            VARCHAR NOT NULL,
    price_date             DATE,
    eps                    DOUBLE,
    book_value_per_share   DOUBLE,
    shares_outstanding     DOUBLE,
    fundamental_period     VARCHAR,      -- fiscal_year:fiscal_period:scope
    fundamental_published_at DATE,
    sector_code            VARCHAR,
    taxonomy_version       VARCHAR,
    pe_ratio               DOUBLE,
    earnings_yield         DOUBLE,
    pb_ratio               DOUBLE,
    book_yield             DOUBLE,
    historical_pe_percentile DOUBLE,
    sector_pe_percentile   DOUBLE,
    caveats_json           VARCHAR NOT NULL,
    lineage_json           VARCHAR NOT NULL,
    contract_version       VARCHAR NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(symbol, as_of_date, price_basis)
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

ALL_DDL_VALUATION = (
    VALUATION_SNAPSHOT_DDL,
    VALUATION_SNAPSHOT_IDX,
    VALUATION_SNAPSHOT_IDX_SECTOR,
)

__all__ = ["ALL_DDL_VALUATION"]
