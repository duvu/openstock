from __future__ import annotations

RESEARCH_ANSWER_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS research_answer_audit (
    research_answer_audit_id VARCHAR PRIMARY KEY,
    assistant_session_id     VARCHAR NOT NULL,
    research_session_id      VARCHAR,
    created_at               TIMESTAMPTZ NOT NULL,
    intent                   VARCHAR NOT NULL,
    tools_json               VARCHAR NOT NULL,
    artifact_refs_json       VARCHAR NOT NULL,
    dataset_freshness_json   VARCHAR NOT NULL,
    groundedness_status      VARCHAR NOT NULL,
    groundedness_json        VARCHAR NOT NULL,
    policy_status            VARCHAR NOT NULL,
    policy_json              VARCHAR NOT NULL,
    missing_data_json        VARCHAR,
    caveats_json             VARCHAR NOT NULL,
    correlation_id           VARCHAR
)
"""

ALL_DDL_RESEARCH_ANSWER_AUDIT = [RESEARCH_ANSWER_AUDIT_DDL]

__all__ = ["ALL_DDL_RESEARCH_ANSWER_AUDIT", "RESEARCH_ANSWER_AUDIT_DDL"]
