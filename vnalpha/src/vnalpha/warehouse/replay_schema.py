"""Warehouse DDL for deterministic point-in-time ranking replay artifacts."""

from __future__ import annotations

RANKING_REPLAY_DDL = """
CREATE TABLE IF NOT EXISTS ranking_replay (
    replay_id VARCHAR PRIMARY KEY,
    spec_hash VARCHAR NOT NULL,
    dataset_hash VARCHAR NOT NULL,
    result_hash VARCHAR NOT NULL,
    scoring_policy_id VARCHAR,
    scoring_policy_version VARCHAR,
    scoring_policy_hash VARCHAR,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    horizon_sessions INTEGER NOT NULL,
    top_n INTEGER NOT NULL,
    price_basis VARCHAR NOT NULL,
    benchmark_symbol VARCHAR NOT NULL,
    cost_bps DOUBLE NOT NULL,
    period_count INTEGER NOT NULL,
    total_return DOUBLE,
    mean_period_excess DOUBLE,
    max_drawdown DOUBLE,
    mean_turnover DOUBLE,
    mean_sector_concentration DOUBLE,
    exclusions_json VARCHAR NOT NULL,
    caveats_json VARCHAR NOT NULL,
    spec_json VARCHAR NOT NULL,
    contract_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(spec_hash, dataset_hash)
)
"""

RANKING_REPLAY_PERIOD_DDL = """
CREATE TABLE IF NOT EXISTS ranking_replay_period (
    period_row_id VARCHAR PRIMARY KEY,
    replay_id VARCHAR NOT NULL,
    period_index INTEGER NOT NULL,
    watchlist_date DATE NOT NULL,
    selected_count INTEGER NOT NULL,
    period_excess_return DOUBLE,
    turnover DOUBLE,
    sector_concentration DOUBLE,
    selected_symbols_json VARCHAR NOT NULL,
    FOREIGN KEY (replay_id) REFERENCES ranking_replay(replay_id)
)
"""

RANKING_REPLAY_V2_DDL = """
CREATE TABLE IF NOT EXISTS ranking_replay_v2 (
    replay_id VARCHAR PRIMARY KEY,
    spec_hash VARCHAR NOT NULL,
    dataset_hash VARCHAR NOT NULL,
    result_hash VARCHAR NOT NULL,
    scoring_policy_hash VARCHAR NOT NULL,
    ranking_run_refs_json VARCHAR NOT NULL,
    evaluation_manifest_ids_json VARCHAR NOT NULL,
    eligible_universe_hashes_json VARCHAR NOT NULL,
    membership_resolver_version VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    horizon_sessions INTEGER NOT NULL,
    top_n INTEGER NOT NULL,
    price_basis VARCHAR NOT NULL,
    adjustment_version VARCHAR NOT NULL,
    benchmark_symbol VARCHAR NOT NULL,
    rebalance_frequency VARCHAR NOT NULL,
    holding_policy VARCHAR NOT NULL,
    liquidity_policy_version VARCHAR NOT NULL,
    cost_bps DOUBLE NOT NULL,
    period_count INTEGER NOT NULL,
    compounded_total_return DOUBLE,
    mean_period_excess DOUBLE,
    max_drawdown DOUBLE,
    mean_turnover DOUBLE,
    mean_sector_concentration DOUBLE,
    exclusions_json VARCHAR NOT NULL,
    caveats_json VARCHAR NOT NULL,
    event_ledger_json VARCHAR NOT NULL,
    spec_json VARCHAR NOT NULL,
    contract_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(spec_hash, dataset_hash)
)
"""

RANKING_REPLAY_PERIOD_V2_DDL = """
CREATE TABLE IF NOT EXISTS ranking_replay_period_v2 (
    period_row_id VARCHAR PRIMARY KEY,
    replay_id VARCHAR NOT NULL,
    period_index INTEGER NOT NULL,
    watchlist_date DATE NOT NULL,
    ranking_run_ref VARCHAR NOT NULL,
    eligible_universe_hash VARCHAR NOT NULL,
    selected_count INTEGER NOT NULL,
    period_excess_return DOUBLE,
    equity_value DOUBLE,
    drawdown DOUBLE,
    turnover DOUBLE,
    sector_concentration DOUBLE,
    selected_symbols_json VARCHAR NOT NULL,
    source_outcome_hash VARCHAR NOT NULL,
    FOREIGN KEY (replay_id) REFERENCES ranking_replay_v2(replay_id)
)
"""

RANKING_REPLAY_IDX = """
CREATE INDEX IF NOT EXISTS idx_ranking_replay_period_replay
ON ranking_replay_period(replay_id, period_index)
"""

RANKING_REPLAY_V2_IDX = """
CREATE INDEX IF NOT EXISTS idx_ranking_replay_v2_policy_window
ON ranking_replay_v2(scoring_policy_hash, start_date, end_date)
"""

ALL_DDL_RANKING_REPLAY = (
    RANKING_REPLAY_DDL,
    RANKING_REPLAY_PERIOD_DDL,
    RANKING_REPLAY_V2_DDL,
    RANKING_REPLAY_PERIOD_V2_DDL,
    RANKING_REPLAY_IDX,
    RANKING_REPLAY_V2_IDX,
)

__all__ = ["ALL_DDL_RANKING_REPLAY"]
