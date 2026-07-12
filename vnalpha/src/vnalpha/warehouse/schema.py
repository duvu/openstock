"""DuckDB schema DDL for the vnalpha research warehouse."""

from __future__ import annotations

from vnalpha.warehouse.research_automation_schema import ALL_DDL_RESEARCH_AUTOMATION

INGESTION_RUN_DDL = """
CREATE TABLE IF NOT EXISTS ingestion_run (
    ingestion_run_id  VARCHAR PRIMARY KEY,
    started_at        TIMESTAMPTZ NOT NULL,
    finished_at       TIMESTAMPTZ,
    status            VARCHAR NOT NULL,
    source_service    VARCHAR,
    source_endpoint   VARCHAR,
    universe          VARCHAR,
    params_json       VARCHAR,
    error_json        VARCHAR
)
"""

SYMBOL_MASTER_DDL = """
CREATE TABLE IF NOT EXISTS symbol_master (
    symbol        VARCHAR PRIMARY KEY,
    exchange      VARCHAR,
    name          VARCHAR,
    sector        VARCHAR,
    industry      VARCHAR,
    is_active     BOOLEAN DEFAULT TRUE,
    last_seen_at  TIMESTAMPTZ
)
"""

MARKET_OHLCV_RAW_DDL = """
CREATE TABLE IF NOT EXISTS market_ohlcv_raw (
    ingestion_run_id   VARCHAR NOT NULL,
    symbol             VARCHAR NOT NULL,
    time               TIMESTAMP NOT NULL,
    interval           VARCHAR NOT NULL DEFAULT '1D',
    open               DOUBLE,
    high               DOUBLE,
    low                DOUBLE,
    close              DOUBLE,
    volume             DOUBLE,
    provider           VARCHAR,
    quality_status     VARCHAR,
    quality_report_json VARCHAR,
    diagnostics_json   VARCHAR,
    fetched_at         TIMESTAMPTZ,
    raw_json           VARCHAR,
    PRIMARY KEY (ingestion_run_id, symbol, time, interval)
)
"""

CANONICAL_OHLCV_DDL = """
CREATE TABLE IF NOT EXISTS canonical_ohlcv (
    symbol                  VARCHAR NOT NULL,
    time                    TIMESTAMP NOT NULL,
    interval                VARCHAR NOT NULL DEFAULT '1D',
    open                    DOUBLE,
    high                    DOUBLE,
    low                     DOUBLE,
    close                   DOUBLE,
    volume                  DOUBLE,
    selected_provider       VARCHAR,
    quality_status          VARCHAR,
    ingestion_run_id        VARCHAR,
    source_service_run_id   VARCHAR,
    PRIMARY KEY (symbol, time, interval)
)
"""

FEATURE_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS feature_snapshot (
    symbol                VARCHAR NOT NULL,
    date                  DATE NOT NULL,
    close                 DOUBLE,
    ma20                  DOUBLE,
    ma50                  DOUBLE,
    ma100                 DOUBLE,
    ma20_slope            DOUBLE,
    ma50_slope            DOUBLE,
    volume_ma20           DOUBLE,
    volume_ratio          DOUBLE,
    atr14                 DOUBLE,
    return_20d            DOUBLE,
    return_60d            DOUBLE,
    rs_20d_vs_vnindex     DOUBLE,
    rs_60d_vs_vnindex     DOUBLE,
    distance_to_ma20      DOUBLE,
    distance_to_52w_high  DOUBLE,
    base_range_30d        DOUBLE,
    close_strength        DOUBLE,
    volatility_20d        DOUBLE,
    as_of_bar_date        DATE,
    benchmark_as_of_bar_date DATE,
    source_row_count      INTEGER,
    benchmark_row_count   INTEGER,
    feature_data_status   VARCHAR,
    feature_build_version VARCHAR,
    feature_generated_at  TIMESTAMPTZ,
    lineage_json          VARCHAR,
    PRIMARY KEY (symbol, date)
)
"""

CANDIDATE_SCORE_DDL = """
CREATE TABLE IF NOT EXISTS candidate_score (
    symbol                    VARCHAR NOT NULL,
    date                      DATE NOT NULL,
    score                     DOUBLE NOT NULL,
    candidate_class           VARCHAR NOT NULL,
    setup_type                VARCHAR,
    trend_score               DOUBLE,
    relative_strength_score   DOUBLE,
    volume_score              DOUBLE,
    base_score                DOUBLE,
    breakout_score            DOUBLE,
    risk_quality_score        DOUBLE,
    evidence_json             VARCHAR,
    risk_flags_json           VARCHAR,
    lineage_json              VARCHAR,
    PRIMARY KEY (symbol, date)
)
"""

DAILY_WATCHLIST_DDL = """
CREATE TABLE IF NOT EXISTS daily_watchlist (
    date             DATE NOT NULL,
    rank             INTEGER NOT NULL,
    symbol           VARCHAR NOT NULL,
    score            DOUBLE,
    candidate_class  VARCHAR,
    setup_type       VARCHAR,
    risk_flags_json  VARCHAR,
    lineage_json     VARCHAR,
    created_at       TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (date, rank)
)
"""

REJECTED_SYMBOL_DDL = """
CREATE TABLE IF NOT EXISTS rejected_symbol (
    symbol           VARCHAR NOT NULL,
    date             DATE NOT NULL,
    stage            VARCHAR NOT NULL,
    reason           VARCHAR NOT NULL,
    details_json     VARCHAR,
    ingestion_run_id VARCHAR,
    provider         VARCHAR,
    created_at       TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (symbol, date, stage)
)
"""
# Note: `date` is the affected data/bar date; `created_at` is the detection timestamp.

ALL_DDL = [
    INGESTION_RUN_DDL,
    SYMBOL_MASTER_DDL,
    MARKET_OHLCV_RAW_DDL,
    CANONICAL_OHLCV_DDL,
    FEATURE_SNAPSHOT_DDL,
    CANDIDATE_SCORE_DDL,
    DAILY_WATCHLIST_DDL,
    REJECTED_SYMBOL_DDL,
]

# Phase 5.8 command-layer tables
RESEARCH_SESSION_DDL = """
CREATE TABLE IF NOT EXISTS research_session (
    session_id            VARCHAR PRIMARY KEY,
    started_at            TIMESTAMPTZ NOT NULL,
    finished_at           TIMESTAMPTZ,
    status                VARCHAR NOT NULL,
    surface               VARCHAR NOT NULL,
    command_text          VARCHAR NOT NULL,
    command_name          VARCHAR,
    parsed_args_json      VARCHAR,
    result_summary_json   VARCHAR,
    error_json            VARCHAR
)
"""

TOOL_TRACE_DDL = """
CREATE TABLE IF NOT EXISTS tool_trace (
    tool_trace_id         VARCHAR PRIMARY KEY,
    session_id            VARCHAR,
    assistant_session_id  VARCHAR,
    trace_parent_type     VARCHAR,
    tool_name             VARCHAR NOT NULL,
    started_at            TIMESTAMPTZ NOT NULL,
    finished_at           TIMESTAMPTZ,
    status                VARCHAR NOT NULL,
    input_json            VARCHAR,
    output_summary_json   VARCHAR,
    error_json            VARCHAR
)
"""

RESEARCH_NOTE_DDL = """
CREATE TABLE IF NOT EXISTS research_note (
    note_id               VARCHAR PRIMARY KEY,
    created_at            TIMESTAMPTZ NOT NULL,
    updated_at            TIMESTAMPTZ,
    symbol                VARCHAR,
    session_id            VARCHAR,
    note_text             VARCHAR NOT NULL,
    tags_json             VARCHAR
)
"""

ALL_DDL_PHASE58 = [
    RESEARCH_SESSION_DDL,
    TOOL_TRACE_DDL,
    RESEARCH_NOTE_DDL,
]

# Phase 5.9 assistant-layer tables
ASSISTANT_SESSION_DDL = """
CREATE TABLE IF NOT EXISTS assistant_session (
    assistant_session_id  VARCHAR PRIMARY KEY,
    started_at            TIMESTAMPTZ NOT NULL,
    finished_at           TIMESTAMPTZ,
    status                VARCHAR NOT NULL,
    surface               VARCHAR NOT NULL,
    user_prompt           VARCHAR NOT NULL,
    intent                VARCHAR,
    plan_json             VARCHAR,
    answer_json           VARCHAR,
    refusal_reason        VARCHAR,
    error_json            VARCHAR,
    prompt_text           VARCHAR,
    prompt_summary        VARCHAR,
    prompt_hash           VARCHAR,
    prompt_chars          INTEGER,
    workspace_context_ref VARCHAR,
    chat_context_ref      VARCHAR,
    raw_stored            BOOLEAN DEFAULT FALSE
)
"""

LLM_TRACE_DDL = """
CREATE TABLE IF NOT EXISTS llm_trace (
    llm_trace_id            VARCHAR PRIMARY KEY,
    assistant_session_id    VARCHAR NOT NULL,
    stage                   VARCHAR NOT NULL,
    model                   VARCHAR,
    started_at              TIMESTAMPTZ NOT NULL,
    finished_at             TIMESTAMPTZ,
    status                  VARCHAR NOT NULL,
    input_summary_json      VARCHAR,
    output_summary_json     VARCHAR,
    usage_json              VARCHAR,
    error_json              VARCHAR
)
"""

PREPARED_TURN_DDL = """
CREATE TABLE IF NOT EXISTS prepared_assistant_turn (
    prepared_turn_id       VARCHAR PRIMARY KEY,
    assistant_session_id   VARCHAR NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL,
    request_json            VARCHAR NOT NULL,
    intent_json             VARCHAR NOT NULL,
    plan_json               VARCHAR NOT NULL,
    plan_hash               VARCHAR NOT NULL,
    policy_status           VARCHAR NOT NULL,
    status                  VARCHAR NOT NULL,
    finished_at             TIMESTAMPTZ
)
"""

ALL_DDL_PHASE59 = [
    ASSISTANT_SESSION_DDL,
    LLM_TRACE_DDL,
    PREPARED_TURN_DDL,
]

# Phase 6 outcome-tracking tables
CANDIDATE_OUTCOME_DDL = """
CREATE TABLE IF NOT EXISTS candidate_outcome (
    symbol                   VARCHAR NOT NULL,
    watchlist_date           DATE NOT NULL,
    horizon_sessions         INTEGER NOT NULL,
    rank                     INTEGER,
    score                    DOUBLE,
    candidate_class          VARCHAR,
    setup_type               VARCHAR,
    risk_flags_json          VARCHAR,
    entry_close              DOUBLE,
    exit_close               DOUBLE,
    benchmark_entry_close    DOUBLE,
    benchmark_exit_close     DOUBLE,
    forward_return           DOUBLE,
    benchmark_return         DOUBLE,
    excess_return_vs_vnindex DOUBLE,
    max_gain                 DOUBLE,
    max_drawdown             DOUBLE,
    hit                      BOOLEAN,
    failure                  BOOLEAN,
    outcome_status           VARCHAR NOT NULL,
    bars_available           INTEGER,
    required_bars            INTEGER,
    computed_at              TIMESTAMPTZ,
    error_json               VARCHAR,
    evaluation_run_id        VARCHAR,
    evaluator_version        VARCHAR,
    metric_policy_version    VARCHAR,
    symbol_bar_count         INTEGER,
    benchmark_bar_count      INTEGER,
    PRIMARY KEY (symbol, watchlist_date, horizon_sessions)
)
"""

WATCHLIST_OUTCOME_DDL = """
CREATE TABLE IF NOT EXISTS watchlist_outcome (
    watchlist_date           DATE NOT NULL,
    horizon_sessions         INTEGER NOT NULL,
    candidate_count          INTEGER,
    complete_count           INTEGER,
    pending_count            INTEGER,
    missing_data_count       INTEGER,
    avg_forward_return       DOUBLE,
    median_forward_return    DOUBLE,
    avg_excess_return        DOUBLE,
    median_excess_return     DOUBLE,
    avg_max_gain             DOUBLE,
    avg_max_drawdown         DOUBLE,
    hit_rate                 DOUBLE,
    failure_rate             DOUBLE,
    computed_at              TIMESTAMPTZ,
    evaluation_run_id        VARCHAR,
    evaluator_version        VARCHAR,
    metric_policy_version    VARCHAR,
    PRIMARY KEY (watchlist_date, horizon_sessions)
)
"""

SCORE_BUCKET_PERFORMANCE_DDL = """
CREATE TABLE IF NOT EXISTS score_bucket_performance (
    as_of_date               DATE NOT NULL,
    horizon_sessions         INTEGER NOT NULL,
    score_bucket             VARCHAR NOT NULL,
    candidate_count          INTEGER,
    avg_forward_return       DOUBLE,
    median_forward_return    DOUBLE,
    avg_excess_return        DOUBLE,
    hit_rate                 DOUBLE,
    failure_rate             DOUBLE,
    avg_max_drawdown         DOUBLE,
    computed_at              TIMESTAMPTZ,
    evaluation_run_id        VARCHAR,
    evaluator_version        VARCHAR,
    metric_policy_version    VARCHAR,
    PRIMARY KEY (as_of_date, horizon_sessions, score_bucket)
)
"""

SETUP_TYPE_PERFORMANCE_DDL = """
CREATE TABLE IF NOT EXISTS setup_type_performance (
    as_of_date               DATE NOT NULL,
    horizon_sessions         INTEGER NOT NULL,
    setup_type               VARCHAR NOT NULL,
    candidate_count          INTEGER,
    avg_forward_return       DOUBLE,
    median_forward_return    DOUBLE,
    avg_excess_return        DOUBLE,
    hit_rate                 DOUBLE,
    failure_rate             DOUBLE,
    avg_max_drawdown         DOUBLE,
    computed_at              TIMESTAMPTZ,
    evaluation_run_id        VARCHAR,
    evaluator_version        VARCHAR,
    metric_policy_version    VARCHAR,
    PRIMARY KEY (as_of_date, horizon_sessions, setup_type)
)
"""

RISK_FLAG_PERFORMANCE_DDL = """
CREATE TABLE IF NOT EXISTS risk_flag_performance (
    as_of_date               DATE NOT NULL,
    horizon_sessions         INTEGER NOT NULL,
    risk_flag                VARCHAR NOT NULL,
    candidate_count          INTEGER,
    avg_forward_return       DOUBLE,
    median_forward_return    DOUBLE,
    avg_excess_return        DOUBLE,
    hit_rate                 DOUBLE,
    failure_rate             DOUBLE,
    avg_max_drawdown         DOUBLE,
    computed_at              TIMESTAMPTZ,
    evaluation_run_id        VARCHAR,
    evaluator_version        VARCHAR,
    metric_policy_version    VARCHAR,
    PRIMARY KEY (as_of_date, horizon_sessions, risk_flag)
)
"""

OUTCOME_EVALUATION_RUN_DDL = """
CREATE TABLE IF NOT EXISTS outcome_evaluation_run (
    evaluation_run_id     VARCHAR PRIMARY KEY,
    watchlist_date        DATE NOT NULL,
    started_at            TIMESTAMPTZ NOT NULL,
    finished_at           TIMESTAMPTZ,
    status                VARCHAR NOT NULL,
    evaluator_version     VARCHAR,
    metric_policy_version VARCHAR,
    horizons_json         VARCHAR,
    symbol_bar_count_json VARCHAR,
    benchmark_bar_count   INTEGER,
    evaluated             INTEGER,
    persisted             INTEGER,
    errors                INTEGER,
    error_json            VARCHAR
)
"""

ALL_DDL_PHASE6 = [
    OUTCOME_EVALUATION_RUN_DDL,
    CANDIDATE_OUTCOME_DDL,
    WATCHLIST_OUTCOME_DDL,
    SCORE_BUCKET_PERFORMANCE_DDL,
    SETUP_TYPE_PERFORMANCE_DDL,
    RISK_FLAG_PERFORMANCE_DDL,
]

CHAT_SESSION_DDL = """
CREATE TABLE IF NOT EXISTS chat_session (
    chat_session_id  VARCHAR PRIMARY KEY,
    started_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ,
    status           VARCHAR NOT NULL DEFAULT 'active',
    surface          VARCHAR NOT NULL DEFAULT 'tui-chat',
    target_date      VARCHAR,
    title            VARCHAR,
    context_json     VARCHAR
)
"""

CHAT_MESSAGE_DDL = """
CREATE TABLE IF NOT EXISTS chat_message (
    chat_message_id       VARCHAR PRIMARY KEY,
    chat_session_id       VARCHAR NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL,
    role                  VARCHAR NOT NULL,
    content               VARCHAR NOT NULL,
    message_type          VARCHAR NOT NULL DEFAULT 'plain_text',
    assistant_session_id  VARCHAR,
    research_session_id   VARCHAR,
    tool_trace_ids_json   VARCHAR,
    plan_json             VARCHAR,
    metadata_json         VARCHAR
)
"""

ALL_DDL_PHASE510 = [CHAT_SESSION_DDL, CHAT_MESSAGE_DDL]

MARKET_REGIME_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS market_regime_snapshot (
    as_of_date                  DATE PRIMARY KEY,
    benchmark_symbol            VARCHAR NOT NULL,
    benchmark_bar_date          DATE NOT NULL,
    close                       DOUBLE NOT NULL,
    ma20                        DOUBLE NOT NULL,
    ma50                        DOUBLE NOT NULL,
    ma50_slope                  DOUBLE NOT NULL,
    return20                    DOUBLE,
    return60                    DOUBLE,
    volatility20                DOUBLE NOT NULL,
    breadth_active_count        INTEGER NOT NULL,
    breadth_eligible_count      INTEGER NOT NULL,
    breadth_excluded_count      INTEGER NOT NULL,
    breadth_coverage            DOUBLE,
    pct_above_ma20              DOUBLE,
    pct_above_ma50              DOUBLE,
    pct_positive_return20       DOUBLE,
    regime                      VARCHAR NOT NULL,
    trend                       VARCHAR NOT NULL,
    volatility                  VARCHAR NOT NULL,
    quality                     VARCHAR NOT NULL,
    caveats_json                VARCHAR NOT NULL,
    lineage_json                VARCHAR NOT NULL,
    methodology_version         VARCHAR NOT NULL,
    generated_at                TIMESTAMPTZ NOT NULL
)
"""

SECTOR_STRENGTH_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS sector_strength_snapshot (
    as_of_date                  DATE NOT NULL,
    sector                      VARCHAR NOT NULL,
    rank                        INTEGER NOT NULL,
    member_count                INTEGER NOT NULL,
    eligible_count              INTEGER NOT NULL,
    median_return20             DOUBLE NOT NULL,
    median_return60             DOUBLE NOT NULL,
    median_rs20_vs_vnindex      DOUBLE NOT NULL,
    median_rs60_vs_vnindex      DOUBLE NOT NULL,
    pct_above_ma20              DOUBLE NOT NULL,
    pct_above_ma50              DOUBLE NOT NULL,
    leadership_count            INTEGER NOT NULL,
    score                       DOUBLE NOT NULL,
    rotation                    VARCHAR NOT NULL,
    metadata_coverage           DOUBLE NOT NULL,
    unclassified_count          INTEGER NOT NULL,
    quality                     VARCHAR NOT NULL,
    caveats_json                VARCHAR NOT NULL,
    lineage_json                VARCHAR NOT NULL,
    methodology_version         VARCHAR NOT NULL,
    generated_at                TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (as_of_date, sector)
)
"""

ALL_DDL_MARKET_CONTEXT = [
    MARKET_REGIME_SNAPSHOT_DDL,
    SECTOR_STRENGTH_SNAPSHOT_DDL,
]

ALL_DDL_COMBINED = (
    ALL_DDL
    + ALL_DDL_PHASE58
    + ALL_DDL_PHASE59
    + ALL_DDL_PHASE6
    + ALL_DDL_PHASE510
    + ALL_DDL_RESEARCH_AUTOMATION
    + ALL_DDL_MARKET_CONTEXT
)
