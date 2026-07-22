"""Maintenance run and stage ledger schema for issue #252."""

DDL_MAINTENANCE_RUN = """
CREATE TABLE IF NOT EXISTS maintenance_run (
    run_id VARCHAR PRIMARY KEY,
    correlation_id VARCHAR NOT NULL,
    requested_date VARCHAR,
    resolved_date VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    requested_symbol_count INTEGER NOT NULL,
    successful_symbol_count INTEGER NOT NULL,
    failed_symbol_count INTEGER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    duration_seconds DOUBLE NOT NULL,
    software_version VARCHAR NOT NULL,
    package_version VARCHAR,
    source_commit VARCHAR,
    tree_state VARCHAR,
    calendar_version VARCHAR,
    mutated BOOLEAN NOT NULL DEFAULT FALSE,
    diagnostics_refs JSON,
    source_policy JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DDL_MAINTENANCE_RUN_PACKAGE_VERSION = """
ALTER TABLE maintenance_run ADD COLUMN IF NOT EXISTS package_version VARCHAR;
"""

DDL_MAINTENANCE_RUN_SOURCE_COMMIT = """
ALTER TABLE maintenance_run ADD COLUMN IF NOT EXISTS source_commit VARCHAR;
"""

DDL_MAINTENANCE_RUN_TREE_STATE = """
ALTER TABLE maintenance_run ADD COLUMN IF NOT EXISTS tree_state VARCHAR;
"""

DDL_MAINTENANCE_STAGE_RUN = """
CREATE TABLE IF NOT EXISTS maintenance_stage_run (
    stage_run_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    stage_name VARCHAR NOT NULL,
    stage_order INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    counts JSON,
    failures JSON,
    warnings JSON,
    diagnostics_refs JSON,
    remediation JSON,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES maintenance_run(run_id)
);
"""

DDL_MAINTENANCE_RUN_IDX_COMPLETED_AT = """
CREATE INDEX IF NOT EXISTS idx_maintenance_run_completed_at
ON maintenance_run(completed_at DESC);
"""

DDL_MAINTENANCE_RUN_IDX_STATUS = """
CREATE INDEX IF NOT EXISTS idx_maintenance_run_status
ON maintenance_run(status, completed_at DESC);
"""

DDL_MAINTENANCE_RUN_QUEUE_COLUMNS = (
    "ALTER TABLE maintenance_run ADD COLUMN IF NOT EXISTS universe_snapshot_id VARCHAR",
    "ALTER TABLE maintenance_run ADD COLUMN IF NOT EXISTS universe_hash VARCHAR",
    "ALTER TABLE maintenance_run ADD COLUMN IF NOT EXISTS symbols_json JSON",
    "ALTER TABLE maintenance_run ADD COLUMN IF NOT EXISTS expected_goals_json JSON",
    "ALTER TABLE maintenance_run ADD COLUMN IF NOT EXISTS source_policy_version VARCHAR",
)

DDL_MAINTENANCE_RUN_JOB = """
CREATE TABLE IF NOT EXISTS maintenance_run_job (
    maintenance_run_id VARCHAR NOT NULL,
    goal_identity VARCHAR NOT NULL,
    goal_type VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    goal_payload_json VARCHAR NOT NULL,
    job_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mapped_at TIMESTAMP,
    PRIMARY KEY (maintenance_run_id, goal_identity)
)
"""

DDL_MAINTENANCE_RUN_JOB_IDX = """
CREATE INDEX IF NOT EXISTS idx_maintenance_run_job_job_id
ON maintenance_run_job(job_id);
"""

DDL_MAINTENANCE_STAGE_RUN_IDX_RUN = """
CREATE INDEX IF NOT EXISTS idx_maintenance_stage_run_run_id
ON maintenance_stage_run(run_id, stage_order);
"""

ALL_DDL_MAINTENANCE_LEDGER = (
    DDL_MAINTENANCE_RUN,
    DDL_MAINTENANCE_RUN_PACKAGE_VERSION,
    DDL_MAINTENANCE_RUN_SOURCE_COMMIT,
    DDL_MAINTENANCE_RUN_TREE_STATE,
    DDL_MAINTENANCE_STAGE_RUN,
    DDL_MAINTENANCE_RUN_IDX_COMPLETED_AT,
    DDL_MAINTENANCE_RUN_IDX_STATUS,
    DDL_MAINTENANCE_STAGE_RUN_IDX_RUN,
    DDL_MAINTENANCE_RUN_JOB,
    DDL_MAINTENANCE_RUN_JOB_IDX,
)
