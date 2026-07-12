"""DuckDB schema DDL for research automation metadata."""

from __future__ import annotations

from typing import Final

RESEARCH_ARTIFACT_DDL: Final = """
CREATE TABLE IF NOT EXISTS research_artifact (
    artifact_id VARCHAR PRIMARY KEY,
    artifact_type VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    purpose VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    created_by VARCHAR NOT NULL,
    run_id VARCHAR,
    correlation_id VARCHAR NOT NULL CHECK (length(correlation_id) BETWEEN 8 AND 64),
    status VARCHAR NOT NULL CHECK (status IN (
        'created', 'running', 'succeeded',
        'failed', 'rejected', 'validated', 'promoted'
    )),
    lifecycle_state VARCHAR NOT NULL CHECK (
        lifecycle_state IN (
            'RUN', 'OBSERVE', 'PACKAGE', 'AI_FIX', 'VALIDATE',
            'PROMOTE_READY', 'PROMOTED', 'REJECTED', 'ROLLED_BACK',
            'FAILED'
        )
    ),
    sandbox_job_id VARCHAR,
    related_experiment_id VARCHAR,
    related_feature_id VARCHAR,
    related_hypothesis_id VARCHAR,
    related_pattern_id VARCHAR,
    related_offline_event_study_id VARCHAR,
    input_datasets_json VARCHAR NOT NULL,
    parameters_json VARCHAR NOT NULL,
    metrics_json VARCHAR NOT NULL,
    lineage_json VARCHAR NOT NULL,
    quality_status_json VARCHAR NOT NULL,
    caveats_json VARCHAR NOT NULL,
    outputs_json VARCHAR NOT NULL,
    artifact_root_path VARCHAR NOT NULL,
    manifest_path VARCHAR NOT NULL,
    result_path VARCHAR NOT NULL,
    summary_path VARCHAR NOT NULL,
    lineage_path VARCHAR NOT NULL,
    validation_path VARCHAR NOT NULL,
    reproducibility_manifest_path VARCHAR,
    generated_code_path VARCHAR,
    created_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    updated_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    CHECK (json_valid(input_datasets_json)),
    CHECK (json_valid(parameters_json)),
    CHECK (json_valid(metrics_json)),
    CHECK (json_valid(lineage_json)),
    CHECK (json_valid(quality_status_json)),
    CHECK (json_valid(caveats_json)),
    CHECK (json_valid(outputs_json)),
)
"""

RESEARCH_EXPERIMENT_DDL: Final = """
CREATE TABLE IF NOT EXISTS research_experiment (
    artifact_id VARCHAR PRIMARY KEY,
    definition VARCHAR NOT NULL,
    universe VARCHAR,
    start_date DATE,
    end_date DATE,
    horizon_sessions INTEGER CHECK (horizon_sessions IS NULL OR horizon_sessions > 0),
    definition_json VARCHAR NOT NULL,
    created_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    updated_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    CHECK (json_valid(definition_json))
)
"""

RESEARCH_FEATURE_DDL: Final = """
CREATE TABLE IF NOT EXISTS research_feature (
    artifact_id VARCHAR PRIMARY KEY,
    feature_name VARCHAR NOT NULL,
    feature_expression VARCHAR NOT NULL,
    universe VARCHAR,
    definition_json VARCHAR NOT NULL,
    created_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    updated_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    CHECK (json_valid(definition_json))
)
"""

RESEARCH_HYPOTHESIS_DDL: Final = """
CREATE TABLE IF NOT EXISTS research_hypothesis (
    artifact_id VARCHAR PRIMARY KEY,
    hypothesis_text VARCHAR NOT NULL,
    outcome_metric VARCHAR,
    horizon_sessions INTEGER CHECK (horizon_sessions IS NULL OR horizon_sessions > 0),
    event_condition VARCHAR,
    definition_json VARCHAR NOT NULL,
    created_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    updated_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    CHECK (json_valid(definition_json))
)
"""

RESEARCH_PATTERN_SCAN_DDL: Final = """
CREATE TABLE IF NOT EXISTS research_pattern_scan (
    artifact_id VARCHAR PRIMARY KEY,
    pattern_description VARCHAR NOT NULL,
    universe VARCHAR,
    scan_date DATE,
    definition_json VARCHAR NOT NULL,
    created_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    updated_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    CHECK (json_valid(definition_json))
)
"""

RESEARCH_OFFLINE_EVENT_STUDY_DDL: Final = """
CREATE TABLE IF NOT EXISTS research_offline_event_study (
    artifact_id VARCHAR PRIMARY KEY,
    event_definition VARCHAR NOT NULL,
    entry_condition VARCHAR NOT NULL,
    exit_condition VARCHAR,
    horizon_sessions INTEGER CHECK (horizon_sessions IS NULL OR horizon_sessions > 0),
    universe VARCHAR,
    start_date DATE,
    end_date DATE,
    definition_json VARCHAR NOT NULL,
    created_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    updated_at_ts TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    CHECK (json_valid(definition_json))
)
"""

ALL_DDL_RESEARCH_AUTOMATION: Final = [
    RESEARCH_ARTIFACT_DDL,
    RESEARCH_EXPERIMENT_DDL,
    RESEARCH_FEATURE_DDL,
    RESEARCH_HYPOTHESIS_DDL,
    RESEARCH_PATTERN_SCAN_DDL,
    RESEARCH_OFFLINE_EVENT_STUDY_DDL,
    "CREATE INDEX IF NOT EXISTS research_artifact_status_idx ON research_artifact (status)",
    "CREATE INDEX IF NOT EXISTS research_artifact_lifecycle_state_idx ON research_artifact (lifecycle_state)",
    "CREATE INDEX IF NOT EXISTS research_artifact_type_idx ON research_artifact (artifact_type)",
]
