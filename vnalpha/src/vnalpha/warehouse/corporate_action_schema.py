"""Warehouse DDL for provider-independent corporate-action evidence."""

CORPORATE_ACTION_RAW_EVIDENCE_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action_raw_evidence (
    raw_evidence_id       VARCHAR PRIMARY KEY,
    ingestion_run_id      VARCHAR NOT NULL,
    provider              VARCHAR NOT NULL,
    provider_event_id     VARCHAR NOT NULL,
    symbol                VARCHAR NOT NULL,
    source_reference      VARCHAR NOT NULL,
    source_version        VARCHAR NOT NULL,
    content_hash          VARCHAR NOT NULL,
    observed_at           TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    payload_json          VARCHAR NOT NULL,
    quality_status        VARCHAR,
    diagnostics_json      VARCHAR
)
"""

CORPORATE_ACTION_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action (
    revision_id           VARCHAR PRIMARY KEY,
    action_id             VARCHAR NOT NULL,
    revision_number       INTEGER NOT NULL,
    symbol                VARCHAR NOT NULL,
    action_type           VARCHAR NOT NULL,
    announced_at          DATE,
    ex_date               DATE,
    record_date           DATE,
    effective_date        DATE,
    cash_amount           DOUBLE,
    ratio                 DOUBLE,
    ratio_text            VARCHAR,
    subscription_price    DOUBLE,
    reference_price       DOUBLE,
    currency              VARCHAR,
    title                 VARCHAR,
    revision_hash         VARCHAR NOT NULL,
    canonical_status      VARCHAR NOT NULL,
    supersedes_revision_id VARCHAR,
    superseded_by_revision_id VARCHAR,
    affected_from_date    DATE,
    affected_to_date      DATE,
    contract_version      VARCHAR NOT NULL,
    first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    last_seen_at          TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    diagnostics_json      VARCHAR,
    UNIQUE(action_id, revision_number)
)
"""

CORPORATE_ACTION_SOURCE_LINK_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action_source_link (
    provider              VARCHAR NOT NULL,
    provider_event_id     VARCHAR NOT NULL,
    raw_evidence_id       VARCHAR NOT NULL,
    action_id             VARCHAR NOT NULL,
    revision_id           VARCHAR NOT NULL,
    source_authority      VARCHAR NOT NULL,
    linked_at             TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (provider, provider_event_id, raw_evidence_id)
)
"""

CORPORATE_ACTION_QUARANTINE_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action_quarantine (
    quarantine_id         VARCHAR PRIMARY KEY,
    ingestion_run_id      VARCHAR NOT NULL,
    provider              VARCHAR NOT NULL,
    provider_event_id     VARCHAR,
    symbol                VARCHAR,
    rule_ids_json         VARCHAR NOT NULL,
    raw_evidence_id       VARCHAR,
    raw_json              VARCHAR NOT NULL,
    diagnostics_json      VARCHAR,
    quarantined_at        TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
)
"""

CORPORATE_ACTION_AFFECTED_RANGE_DDL = """
CREATE TABLE IF NOT EXISTS corporate_action_affected_range (
    signal_id             VARCHAR PRIMARY KEY,
    action_id             VARCHAR NOT NULL,
    revision_id           VARCHAR NOT NULL,
    symbol                VARCHAR NOT NULL,
    affected_from_date    DATE NOT NULL,
    affected_to_date      DATE,
    reason                VARCHAR NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    resolved_at           TIMESTAMPTZ,
    resolution_ref        VARCHAR
)
"""

ALL_DDL_CORPORATE_ACTIONS = [
    CORPORATE_ACTION_RAW_EVIDENCE_DDL,
    CORPORATE_ACTION_DDL,
    CORPORATE_ACTION_SOURCE_LINK_DDL,
    CORPORATE_ACTION_QUARANTINE_DDL,
    CORPORATE_ACTION_AFFECTED_RANGE_DDL,
]
