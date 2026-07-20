"""Warehouse DDL for deterministic point-in-time ranking replay (issue #262).

Persists one content-hashed replay: the fixed specification, the dataset
fingerprint it consumed, and the reproducible result. Identical inputs reproduce
identical hashes; future-data contamination fails closed before persistence.
"""

from __future__ import annotations

RANKING_REPLAY_DDL = """
CREATE TABLE IF NOT EXISTS ranking_replay (
    replay_id              VARCHAR PRIMARY KEY,
    spec_hash              VARCHAR NOT NULL,
    dataset_hash           VARCHAR NOT NULL,
    result_hash            VARCHAR NOT NULL,
    scoring_policy_id      VARCHAR,
    scoring_policy_version VARCHAR,
    scoring_policy_hash    VARCHAR,
    start_date             DATE NOT NULL,
    end_date               DATE NOT NULL,
    horizon_sessions       INTEGER NOT NULL,
    top_n                  INTEGER NOT NULL,
    price_basis            VARCHAR NOT NULL,
    benchmark_symbol       VARCHAR NOT NULL,
    cost_bps               DOUBLE NOT NULL,
    period_count           INTEGER NOT NULL,
    total_return           DOUBLE,
    mean_period_excess     DOUBLE,
    max_drawdown           DOUBLE,
    mean_turnover          DOUBLE,
    mean_sector_concentration DOUBLE,
    exclusions_json        VARCHAR NOT NULL,
    caveats_json           VARCHAR NOT NULL,
    spec_json              VARCHAR NOT NULL,
    contract_version       VARCHAR NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(spec_hash, dataset_hash)
)
"""

RANKING_REPLAY_PERIOD_DDL = """
CREATE TABLE IF NOT EXISTS ranking_replay_period (
    period_row_id          VARCHAR PRIMARY KEY,
    replay_id              VARCHAR NOT NULL,
    period_index           INTEGER NOT NULL,
    watchlist_date         DATE NOT NULL,
    selected_count         INTEGER NOT NULL,
    period_excess_return   DOUBLE,
    turnover               DOUBLE,
    sector_concentration   DOUBLE,
    selected_symbols_json  VARCHAR NOT NULL,
    FOREIGN KEY (replay_id) REFERENCES ranking_replay(replay_id)
)
"""

RANKING_REPLAY_IDX = """
CREATE INDEX IF NOT EXISTS idx_ranking_replay_period_replay
ON ranking_replay_period(replay_id, period_index)
"""

ALL_DDL_RANKING_REPLAY = (
    RANKING_REPLAY_DDL,
    RANKING_REPLAY_PERIOD_DDL,
    RANKING_REPLAY_IDX,
)

__all__ = ["ALL_DDL_RANKING_REPLAY"]
