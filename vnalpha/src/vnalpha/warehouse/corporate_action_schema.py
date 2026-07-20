"""Warehouse DDL for provider-independent corporate-action evidence."""

CORPORATE_ACTION_RAW_EVIDENCE_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action_raw_evidence (
    raw_evidence_id VARCHAR PRIMARY KEY,
    ingestion_run_id VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    provider_event_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    source_reference VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    content_hash VARCHAR NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    payload_json VARCHAR NOT NULL,
    quality_status VARCHAR,
    diagnostics_json VARCHAR
)
"""

CORPORATE_ACTION_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action (
    revision_id VARCHAR PRIMARY KEY,
    action_id VARCHAR NOT NULL,
    revision_number INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL,
    announced_at DATE,
    ex_date DATE,
    record_date DATE,
    effective_date DATE,
    cash_amount DOUBLE,
    ratio DOUBLE,
    ratio_text VARCHAR,
    subscription_price DOUBLE,
    reference_price DOUBLE,
    currency VARCHAR,
    title VARCHAR,
    revision_hash VARCHAR NOT NULL,
    canonical_status VARCHAR NOT NULL,
    supersedes_revision_id VARCHAR,
    superseded_by_revision_id VARCHAR,
    affected_from_date DATE,
    affected_to_date DATE,
    contract_version VARCHAR NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    diagnostics_json VARCHAR,
    UNIQUE(action_id, revision_number)
)
"""

CORPORATE_ACTION_SOURCE_LINK_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action_source_link (
    provider VARCHAR NOT NULL,
    provider_event_id VARCHAR NOT NULL,
    raw_evidence_id VARCHAR NOT NULL,
    action_id VARCHAR NOT NULL,
    revision_id VARCHAR NOT NULL,
    source_authority VARCHAR NOT NULL,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (provider, provider_event_id, raw_evidence_id)
)
"""

CORPORATE_ACTION_QUARANTINE_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action_quarantine (
    quarantine_id VARCHAR PRIMARY KEY,
    ingestion_run_id VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    provider_event_id VARCHAR,
    symbol VARCHAR,
    rule_ids_json VARCHAR NOT NULL,
    raw_evidence_id VARCHAR,
    raw_json VARCHAR NOT NULL,
    diagnostics_json VARCHAR,
    quarantined_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
)
"""

CORPORATE_ACTION_AFFECTED_RANGE_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action_affected_range (
    signal_id VARCHAR PRIMARY KEY,
    action_id VARCHAR NOT NULL,
    revision_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    affected_from_date DATE NOT NULL,
    affected_to_date DATE,
    reason VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    resolved_at TIMESTAMPTZ,
    resolution_ref VARCHAR
)
"""

ADJUSTMENT_FACTOR_DDL = """
CREATE TABLE IF NOT EXISTS adjustment_factor (
    factor_id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    action_id VARCHAR NOT NULL,
    action_revision_id VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL,
    effective_date DATE NOT NULL,
    price_multiplier DOUBLE NOT NULL,
    volume_multiplier DOUBLE NOT NULL,
    methodology_version VARCHAR NOT NULL,
    content_hash VARCHAR NOT NULL,
    canonical_status VARCHAR NOT NULL,
    supersedes_factor_id VARCHAR,
    superseded_by_factor_id VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(action_revision_id, methodology_version)
)
"""

ADJUSTED_OHLCV_DDL = """
CREATE TABLE IF NOT EXISTS adjusted_ohlcv (
    symbol VARCHAR NOT NULL,
    time TIMESTAMP NOT NULL,
    interval VARCHAR NOT NULL DEFAULT '1D',
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    price_basis VARCHAR NOT NULL,
    adjustment_version VARCHAR NOT NULL,
    factor_chain_hash VARCHAR NOT NULL,
    source_ingestion_run_id VARCHAR,
    source_provider VARCHAR,
    built_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (symbol, time, interval, price_basis, adjustment_version)
)
"""

FEATURE_PRICE_BASIS_DDL = """
ALTER TABLE feature_snapshot ADD COLUMN IF NOT EXISTS price_basis VARCHAR DEFAULT 'RAW_UNADJUSTED'
"""
FEATURE_ADJUSTMENT_VERSION_DDL = """
ALTER TABLE feature_snapshot ADD COLUMN IF NOT EXISTS adjustment_version VARCHAR DEFAULT 'NONE'
"""
FEATURE_FACTOR_CHAIN_DDL = """
ALTER TABLE feature_snapshot ADD COLUMN IF NOT EXISTS factor_chain_hash VARCHAR
"""
SCORE_PRICE_BASIS_DDL = """
ALTER TABLE candidate_score ADD COLUMN IF NOT EXISTS price_basis VARCHAR DEFAULT 'RAW_UNADJUSTED'
"""
SCORE_ADJUSTMENT_VERSION_DDL = """
ALTER TABLE candidate_score ADD COLUMN IF NOT EXISTS adjustment_version VARCHAR DEFAULT 'NONE'
"""
SCORE_FACTOR_CHAIN_DDL = """
ALTER TABLE candidate_score ADD COLUMN IF NOT EXISTS factor_chain_hash VARCHAR
"""
WATCHLIST_PRICE_BASIS_DDL = """
ALTER TABLE daily_watchlist ADD COLUMN IF NOT EXISTS price_basis VARCHAR DEFAULT 'RAW_UNADJUSTED'
"""
WATCHLIST_ADJUSTMENT_VERSION_DDL = """
ALTER TABLE daily_watchlist ADD COLUMN IF NOT EXISTS adjustment_version VARCHAR DEFAULT 'NONE'
"""
WATCHLIST_FACTOR_CHAIN_DDL = """
ALTER TABLE daily_watchlist ADD COLUMN IF NOT EXISTS factor_chain_hash VARCHAR
"""
OUTCOME_FACTOR_CHAIN_DDL = """
ALTER TABLE candidate_outcome ADD COLUMN IF NOT EXISTS factor_chain_hash VARCHAR
"""

ALL_DDL_CORPORATE_ACTIONS = [
    CORPORATE_ACTION_RAW_EVIDENCE_DDL,
    CORPORATE_ACTION_DDL,
    CORPORATE_ACTION_SOURCE_LINK_DDL,
    CORPORATE_ACTION_QUARANTINE_DDL,
    CORPORATE_ACTION_AFFECTED_RANGE_DDL,
    ADJUSTMENT_FACTOR_DDL,
    ADJUSTED_OHLCV_DDL,
    FEATURE_PRICE_BASIS_DDL,
    FEATURE_ADJUSTMENT_VERSION_DDL,
    FEATURE_FACTOR_CHAIN_DDL,
    SCORE_PRICE_BASIS_DDL,
    SCORE_ADJUSTMENT_VERSION_DDL,
    SCORE_FACTOR_CHAIN_DDL,
    WATCHLIST_PRICE_BASIS_DDL,
    WATCHLIST_ADJUSTMENT_VERSION_DDL,
    WATCHLIST_FACTOR_CHAIN_DDL,
    OUTCOME_FACTOR_CHAIN_DDL,
]
