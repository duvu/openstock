"""Warehouse DDL for the publication-aware fundamentals vertical (issue #257).

Stores provider-independent financial facts with immutable source revisions and
explicit publication metadata so historical analysis can build an as-of snapshot
without leaking facts published after the requested date.
"""

from __future__ import annotations

# Immutable per-revision financial-fact rows. A restatement is a NEW revision
# that supersedes a prior one; rows are never mutated in place.
FUNDAMENTAL_FACT_DDL = """
CREATE TABLE IF NOT EXISTS fundamental_fact (
    revision_id            VARCHAR PRIMARY KEY,
    fact_id                VARCHAR NOT NULL,
    revision_number        INTEGER NOT NULL,
    symbol                 VARCHAR NOT NULL,
    fiscal_year            INTEGER NOT NULL,
    fiscal_period          VARCHAR NOT NULL,   -- FY, Q1, Q2, Q3, Q4, H1, H2
    statement_scope        VARCHAR NOT NULL,   -- CONSOLIDATED, SEPARATE
    published_at           DATE NOT NULL,      -- when the fact became public
    available_from         TIMESTAMPTZ NOT NULL, -- earliest as-of usability
    period_end_date        DATE NOT NULL,
    audit_status           VARCHAR NOT NULL,   -- AUDITED, UNAUDITED, REVIEWED
    currency               VARCHAR NOT NULL,
    unit                   VARCHAR NOT NULL,   -- e.g. VND, VND_MILLION
    revenue                DOUBLE,
    net_income             DOUBLE,
    eps                    DOUBLE,
    total_assets           DOUBLE,
    total_equity           DOUBLE,
    total_liabilities      DOUBLE,
    operating_cash_flow    DOUBLE,
    source_reference       VARCHAR NOT NULL,
    source_authority       VARCHAR NOT NULL,
    content_hash           VARCHAR NOT NULL,
    revision_hash          VARCHAR NOT NULL,
    canonical_status       VARCHAR NOT NULL,   -- CURRENT, SUPERSEDED
    supersedes_revision_id VARCHAR,
    superseded_by_revision_id VARCHAR,
    contract_version       VARCHAR NOT NULL,
    first_seen_at          TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    diagnostics_json       VARCHAR,
    UNIQUE(fact_id, revision_number)
)
"""

FUNDAMENTAL_FACT_IDX_SYMBOL = """
CREATE INDEX IF NOT EXISTS idx_fundamental_fact_symbol
ON fundamental_fact(symbol, statement_scope, published_at)
"""

FUNDAMENTAL_FACT_IDX_PERIOD = """
CREATE INDEX IF NOT EXISTS idx_fundamental_fact_period
ON fundamental_fact(symbol, fiscal_year, fiscal_period, statement_scope)
"""

ALL_DDL_FUNDAMENTALS = (
    FUNDAMENTAL_FACT_DDL,
    FUNDAMENTAL_FACT_IDX_SYMBOL,
    FUNDAMENTAL_FACT_IDX_PERIOD,
)

__all__ = ["ALL_DDL_FUNDAMENTALS"]
