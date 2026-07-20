"""Warehouse DDL for the manual RankingPolicy promotion evidence gate."""

from __future__ import annotations

RANKING_POLICY_DECISION_DDL = """
CREATE TABLE IF NOT EXISTS ranking_policy_decision (
    decision_id VARCHAR PRIMARY KEY,
    policy_id VARCHAR NOT NULL,
    policy_version VARCHAR NOT NULL,
    policy_hash VARCHAR NOT NULL,
    decision_status VARCHAR NOT NULL,
    rule_version VARCHAR NOT NULL,
    evidence_cutoff_date DATE NOT NULL,
    sample_count INTEGER NOT NULL,
    period_count INTEGER NOT NULL,
    coverage DOUBLE NOT NULL,
    reviewer VARCHAR NOT NULL,
    rationale VARCHAR NOT NULL,
    limitations_json VARCHAR NOT NULL,
    evaluation_manifest_ids_json VARCHAR NOT NULL,
    replay_ids_json VARCHAR NOT NULL,
    ranking_run_refs_json VARCHAR NOT NULL,
    activates_policy BOOLEAN NOT NULL DEFAULT FALSE,
    contract_version VARCHAR NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
)
"""

RANKING_POLICY_DECISION_BUNDLE_HASH_DDL = """
ALTER TABLE ranking_policy_decision
ADD COLUMN IF NOT EXISTS evidence_bundle_hash VARCHAR
"""

RANKING_POLICY_DECISION_VERIFICATION_DDL = """
ALTER TABLE ranking_policy_decision
ADD COLUMN IF NOT EXISTS evidence_verification_status VARCHAR
"""

RANKING_POLICY_DECISION_ASSUMPTIONS_DDL = """
ALTER TABLE ranking_policy_decision
ADD COLUMN IF NOT EXISTS assumptions_hashes_json VARCHAR
"""

RANKING_POLICY_DECISION_DATASET_HASHES_DDL = """
ALTER TABLE ranking_policy_decision
ADD COLUMN IF NOT EXISTS dataset_hashes_json VARCHAR
"""

RANKING_POLICY_DECISION_IDX = """
CREATE INDEX IF NOT EXISTS idx_ranking_policy_decision_policy
ON ranking_policy_decision(policy_id, policy_version, reviewed_at)
"""

ALL_DDL_RANKING_POLICY_DECISION = (
    RANKING_POLICY_DECISION_DDL,
    RANKING_POLICY_DECISION_BUNDLE_HASH_DDL,
    RANKING_POLICY_DECISION_VERIFICATION_DDL,
    RANKING_POLICY_DECISION_ASSUMPTIONS_DDL,
    RANKING_POLICY_DECISION_DATASET_HASHES_DDL,
    RANKING_POLICY_DECISION_IDX,
)

__all__ = ["ALL_DDL_RANKING_POLICY_DECISION"]
