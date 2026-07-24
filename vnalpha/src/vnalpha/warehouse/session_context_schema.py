SESSION_CONTEXT_REVISION_DDL = """
CREATE TABLE IF NOT EXISTS session_context_revision (
    revision_id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    session_date DATE NOT NULL,
    provider VARCHAR,
    observed_at TIMESTAMPTZ NOT NULL,
    status VARCHAR NOT NULL,
    content_hash VARCHAR,
    summary_json VARCHAR,
    failure_category VARCHAR,
    UNIQUE(symbol, session_date, provider, content_hash)
)
"""

SESSION_CONTEXT_REVISION_INDEX = """
CREATE INDEX IF NOT EXISTS session_context_revision_latest_idx
ON session_context_revision(symbol, session_date, observed_at DESC)
"""

ALL_DDL_SESSION_CONTEXT = (
    SESSION_CONTEXT_REVISION_DDL,
    SESSION_CONTEXT_REVISION_INDEX,
)
