COMPANY_CONTEXT_REVISION_DDL = """
CREATE TABLE IF NOT EXISTS company_context_revision (
    revision_id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    provider VARCHAR,
    observed_at TIMESTAMPTZ NOT NULL,
    status VARCHAR NOT NULL,
    content_hash VARCHAR,
    payload_json VARCHAR,
    failure_category VARCHAR,
    UNIQUE(symbol, provider, content_hash)
)
"""

COMPANY_CONTEXT_REVISION_INDEX = """
CREATE INDEX IF NOT EXISTS company_context_revision_latest_idx
ON company_context_revision(symbol, observed_at DESC)
"""

ALL_DDL_COMPANY_CONTEXT = (
    COMPANY_CONTEXT_REVISION_DDL,
    COMPANY_CONTEXT_REVISION_INDEX,
)
