"""Warehouse DDL for immutable RankingRun baseline evaluation artifacts."""

from __future__ import annotations

CANDIDATE_OUTCOME_RANKING_RUN_REF_DDL = """
ALTER TABLE candidate_outcome ADD COLUMN IF NOT EXISTS ranking_run_ref VARCHAR
"""
CANDIDATE_OUTCOME_UNIVERSE_HASH_DDL = """
ALTER TABLE candidate_outcome ADD COLUMN IF NOT EXISTS eligible_universe_hash VARCHAR
"""
CANDIDATE_OUTCOME_FACTOR_CHAIN_DDL = """
ALTER TABLE candidate_outcome ADD COLUMN IF NOT EXISTS factor_chain_hash VARCHAR
"""

RANKING_EVALUATION_MANIFEST_DDL = """
CREATE TABLE IF NOT EXISTS ranking_evaluation_manifest (
    manifest_id VARCHAR PRIMARY KEY,
    watchlist_date DATE NOT NULL,
    horizon_sessions INTEGER NOT NULL,
    top_n INTEGER NOT NULL,
    price_basis VARCHAR NOT NULL,
    scoring_policy_id VARCHAR,
    scoring_policy_version VARCHAR,
    scoring_policy_hash VARCHAR,
    eligible_population INTEGER NOT NULL,
    complete_population INTEGER NOT NULL,
    sufficiency_status VARCHAR NOT NULL,
    partial_reason VARCHAR,
    assumptions_hash VARCHAR NOT NULL,
    contract_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(watchlist_date, horizon_sessions, top_n, scoring_policy_hash)
)
"""

RANKING_EVALUATION_STRATEGY_DDL = """
CREATE TABLE IF NOT EXISTS ranking_evaluation_strategy (
    strategy_row_id VARCHAR PRIMARY KEY,
    manifest_id VARCHAR NOT NULL,
    strategy VARCHAR NOT NULL,
    sample_count INTEGER NOT NULL,
    coverage DOUBLE,
    hit_rate DOUBLE,
    mean_excess_return DOUBLE,
    median_excess_return DOUBLE,
    mean_max_favorable DOUBLE,
    mean_max_adverse DOUBLE,
    rank_correlation DOUBLE,
    turnover DOUBLE,
    sector_concentration DOUBLE,
    market_regime VARCHAR,
    metrics_json VARCHAR NOT NULL,
    FOREIGN KEY (manifest_id) REFERENCES ranking_evaluation_manifest(manifest_id)
)
"""

RANKING_EVALUATION_MANIFEST_V2_DDL = """
CREATE TABLE IF NOT EXISTS ranking_evaluation_manifest_v2 (
    manifest_id VARCHAR PRIMARY KEY,
    watchlist_date DATE NOT NULL,
    horizon_sessions INTEGER NOT NULL,
    top_n INTEGER NOT NULL,
    price_basis VARCHAR NOT NULL,
    adjustment_version VARCHAR NOT NULL,
    scoring_policy_id VARCHAR NOT NULL,
    scoring_policy_version VARCHAR NOT NULL,
    scoring_policy_hash VARCHAR NOT NULL,
    ranking_run_ref VARCHAR NOT NULL,
    eligible_population INTEGER NOT NULL,
    complete_population INTEGER NOT NULL,
    incomplete_population INTEGER NOT NULL,
    sufficiency_status VARCHAR NOT NULL,
    partial_reason VARCHAR,
    market_regime VARCHAR,
    assumptions_hash VARCHAR NOT NULL,
    eligible_population_hash VARCHAR NOT NULL,
    outcome_rows_hash VARCHAR NOT NULL,
    dataset_hash VARCHAR NOT NULL,
    source_max_computed_at TIMESTAMPTZ,
    contract_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
)
"""

RANKING_EVALUATION_STRATEGY_V2_DDL = """
CREATE TABLE IF NOT EXISTS ranking_evaluation_strategy_v2 (
    strategy_row_id VARCHAR PRIMARY KEY,
    manifest_id VARCHAR NOT NULL,
    strategy VARCHAR NOT NULL,
    selected_symbols_json VARCHAR NOT NULL,
    sample_count INTEGER NOT NULL,
    coverage DOUBLE,
    hit_rate DOUBLE,
    mean_excess_return DOUBLE,
    median_excess_return DOUBLE,
    mean_max_favorable DOUBLE,
    mean_max_adverse DOUBLE,
    rank_correlation DOUBLE,
    turnover DOUBLE,
    sector_concentration DOUBLE,
    market_regime VARCHAR,
    metrics_json VARCHAR NOT NULL,
    FOREIGN KEY (manifest_id) REFERENCES ranking_evaluation_manifest_v2(manifest_id)
)
"""

RANKING_EVALUATION_IDX = """
CREATE INDEX IF NOT EXISTS idx_ranking_eval_strategy_manifest
ON ranking_evaluation_strategy(manifest_id, strategy)
"""

RANKING_EVALUATION_V2_IDX = """
CREATE INDEX IF NOT EXISTS idx_ranking_eval_v2_date_policy
ON ranking_evaluation_manifest_v2(watchlist_date, scoring_policy_hash, horizon_sessions)
"""

ALL_DDL_RANKING_EVALUATION = (
    CANDIDATE_OUTCOME_RANKING_RUN_REF_DDL,
    CANDIDATE_OUTCOME_UNIVERSE_HASH_DDL,
    CANDIDATE_OUTCOME_FACTOR_CHAIN_DDL,
    RANKING_EVALUATION_MANIFEST_DDL,
    RANKING_EVALUATION_STRATEGY_DDL,
    RANKING_EVALUATION_MANIFEST_V2_DDL,
    RANKING_EVALUATION_STRATEGY_V2_DDL,
    RANKING_EVALUATION_IDX,
    RANKING_EVALUATION_V2_IDX,
)

__all__ = ["ALL_DDL_RANKING_EVALUATION"]
