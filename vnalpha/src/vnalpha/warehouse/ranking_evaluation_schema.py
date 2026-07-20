"""Warehouse DDL for RankingRun baseline evaluation (issue #261).

Persists one immutable evaluation manifest per (watchlist_date, horizon,
top-N) comparison of the packaged RankingPolicy against simple baselines, plus
the per-strategy metric rows. Manifests are never rewritten once persisted.
"""

from __future__ import annotations

RANKING_EVALUATION_MANIFEST_DDL = """
CREATE TABLE IF NOT EXISTS ranking_evaluation_manifest (
    manifest_id            VARCHAR PRIMARY KEY,
    watchlist_date         DATE NOT NULL,
    horizon_sessions       INTEGER NOT NULL,
    top_n                  INTEGER NOT NULL,
    price_basis            VARCHAR NOT NULL,
    scoring_policy_id      VARCHAR,
    scoring_policy_version VARCHAR,
    scoring_policy_hash    VARCHAR,
    eligible_population    INTEGER NOT NULL,
    complete_population    INTEGER NOT NULL,
    sufficiency_status     VARCHAR NOT NULL,  -- SUFFICIENT, INSUFFICIENT
    partial_reason         VARCHAR,
    assumptions_hash       VARCHAR NOT NULL,
    contract_version       VARCHAR NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(watchlist_date, horizon_sessions, top_n, scoring_policy_hash)
)
"""

RANKING_EVALUATION_STRATEGY_DDL = """
CREATE TABLE IF NOT EXISTS ranking_evaluation_strategy (
    strategy_row_id        VARCHAR PRIMARY KEY,
    manifest_id            VARCHAR NOT NULL,
    strategy               VARCHAR NOT NULL,  -- packaged, momentum_only, equal_weight, unfiltered
    sample_count           INTEGER NOT NULL,
    coverage               DOUBLE,
    hit_rate               DOUBLE,
    mean_excess_return     DOUBLE,
    median_excess_return   DOUBLE,
    mean_max_favorable     DOUBLE,
    mean_max_adverse       DOUBLE,
    rank_correlation       DOUBLE,
    turnover               DOUBLE,
    sector_concentration   DOUBLE,
    market_regime          VARCHAR,
    metrics_json           VARCHAR NOT NULL,
    FOREIGN KEY (manifest_id) REFERENCES ranking_evaluation_manifest(manifest_id)
)
"""

RANKING_EVALUATION_IDX = """
CREATE INDEX IF NOT EXISTS idx_ranking_eval_strategy_manifest
ON ranking_evaluation_strategy(manifest_id, strategy)
"""

ALL_DDL_RANKING_EVALUATION = (
    RANKING_EVALUATION_MANIFEST_DDL,
    RANKING_EVALUATION_STRATEGY_DDL,
    RANKING_EVALUATION_IDX,
)

__all__ = ["ALL_DDL_RANKING_EVALUATION"]
