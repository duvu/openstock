from __future__ import annotations

import duckdb

from vnalpha.warehouse.migrations import run_migrations


def _create_legacy_research_experiment_table(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    conn.execute(
        "CREATE TABLE research_experiment ("
        "artifact_id VARCHAR PRIMARY KEY,"
        "definition VARCHAR NOT NULL,"
        "universe VARCHAR,"
        "start_date DATE,"
        "end_date DATE,"
        "horizon_sessions INTEGER CHECK (horizon_sessions IS NULL OR horizon_sessions > 0),"
        "definition_json VARCHAR NOT NULL,"
        "created_at_ts TIMESTAMPTZ NOT NULL,"
        "updated_at_ts TIMESTAMPTZ NOT NULL,"
        "CHECK (json_valid(definition_json))"
        ")"
    )


def _create_legacy_research_artifact_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        "CREATE TABLE research_artifact ("
        "artifact_id VARCHAR PRIMARY KEY,"
        "artifact_type VARCHAR NOT NULL,"
        "name VARCHAR NOT NULL,"
        "purpose VARCHAR NOT NULL,"
        "created_at TIMESTAMPTZ NOT NULL,"
        "created_by VARCHAR NOT NULL,"
        "run_id VARCHAR,"
        "correlation_id VARCHAR NOT NULL CHECK (length(correlation_id) BETWEEN 8 AND 64),"
        "status VARCHAR NOT NULL,"
        "sandbox_job_id VARCHAR,"
        "related_experiment_id VARCHAR,"
        "related_feature_id VARCHAR,"
        "related_hypothesis_id VARCHAR,"
        "related_pattern_id VARCHAR,"
        "related_offline_event_study_id VARCHAR,"
        "input_datasets_json VARCHAR NOT NULL,"
        "parameters_json VARCHAR NOT NULL,"
        "metrics_json VARCHAR NOT NULL,"
        "lineage_json VARCHAR NOT NULL,"
        "quality_status_json VARCHAR NOT NULL,"
        "caveats_json VARCHAR NOT NULL,"
        "outputs_json VARCHAR NOT NULL,"
        "artifact_root_path VARCHAR NOT NULL,"
        "manifest_path VARCHAR NOT NULL,"
        "result_path VARCHAR NOT NULL,"
        "summary_path VARCHAR NOT NULL,"
        "lineage_path VARCHAR NOT NULL,"
        "validation_path VARCHAR NOT NULL,"
        "reproducibility_manifest_path VARCHAR,"
        "generated_code_path VARCHAR,"
        "created_at_ts TIMESTAMPTZ NOT NULL,"
        "updated_at_ts TIMESTAMPTZ NOT NULL,"
        "CHECK (json_valid(input_datasets_json)),"
        "CHECK (json_valid(parameters_json)),"
        "CHECK (json_valid(metrics_json)),"
        "CHECK (json_valid(lineage_json)),"
        "CHECK (json_valid(quality_status_json)),"
        "CHECK (json_valid(caveats_json)),"
        "CHECK (json_valid(outputs_json))"
        ")"
    )


def _create_legacy_research_artifact_table_without_lineage_path(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    conn.execute(
        "CREATE TABLE research_artifact ("
        "artifact_id VARCHAR PRIMARY KEY,"
        "artifact_type VARCHAR NOT NULL,"
        "name VARCHAR NOT NULL,"
        "purpose VARCHAR NOT NULL,"
        "created_at TIMESTAMPTZ NOT NULL,"
        "created_by VARCHAR NOT NULL,"
        "run_id VARCHAR,"
        "correlation_id VARCHAR NOT NULL CHECK (length(correlation_id) BETWEEN 8 AND 64),"
        "status VARCHAR NOT NULL,"
        "sandbox_job_id VARCHAR,"
        "related_experiment_id VARCHAR,"
        "related_feature_id VARCHAR,"
        "related_hypothesis_id VARCHAR,"
        "related_pattern_id VARCHAR,"
        "related_offline_event_study_id VARCHAR,"
        "input_datasets_json VARCHAR NOT NULL,"
        "parameters_json VARCHAR NOT NULL,"
        "metrics_json VARCHAR NOT NULL,"
        "lineage_json VARCHAR NOT NULL,"
        "quality_status_json VARCHAR NOT NULL,"
        "caveats_json VARCHAR NOT NULL,"
        "outputs_json VARCHAR NOT NULL,"
        "artifact_root_path VARCHAR NOT NULL,"
        "manifest_path VARCHAR NOT NULL,"
        "result_path VARCHAR NOT NULL,"
        "summary_path VARCHAR NOT NULL,"
        "validation_path VARCHAR NOT NULL,"
        "reproducibility_manifest_path VARCHAR,"
        "generated_code_path VARCHAR,"
        "created_at_ts TIMESTAMPTZ NOT NULL,"
        "updated_at_ts TIMESTAMPTZ NOT NULL,"
        "CHECK (json_valid(input_datasets_json)),"
        "CHECK (json_valid(parameters_json)),"
        "CHECK (json_valid(metrics_json)),"
        "CHECK (json_valid(lineage_json)),"
        "CHECK (json_valid(quality_status_json)),"
        "CHECK (json_valid(caveats_json)),"
        "CHECK (json_valid(outputs_json))"
        ")"
    )


def test_run_migrations_adds_lifecycle_state_to_legacy_research_artifact() -> None:
    conn = duckdb.connect(":memory:")
    _create_legacy_research_artifact_table(conn)

    columns = (
        "artifact_id",
        "artifact_type",
        "name",
        "purpose",
        "created_at",
        "created_by",
        "run_id",
        "correlation_id",
        "status",
        "sandbox_job_id",
        "related_experiment_id",
        "related_feature_id",
        "related_hypothesis_id",
        "related_pattern_id",
        "related_offline_event_study_id",
        "input_datasets_json",
        "parameters_json",
        "metrics_json",
        "lineage_json",
        "quality_status_json",
        "caveats_json",
        "outputs_json",
        "artifact_root_path",
        "manifest_path",
        "result_path",
        "summary_path",
        "lineage_path",
        "validation_path",
        "reproducibility_manifest_path",
        "generated_code_path",
        "created_at_ts",
        "updated_at_ts",
    )
    insert_sql = (
        "INSERT INTO research_artifact ("
        f"{','.join(columns)}) "
        f"VALUES ({','.join(['?'] * len(columns))})"
    )
    for artifact_values in (
        {
            "artifact_id": "ra-1",
            "artifact_type": "indicator_experiment",
            "name": "Artifact 1",
            "purpose": "feature build",
            "created_at": "2026-01-01 00:00:00",
            "created_by": "operator",
            "run_id": None,
            "correlation_id": "corr-legacy",
            "status": "created",
            "sandbox_job_id": None,
            "related_experiment_id": None,
            "related_feature_id": None,
            "related_hypothesis_id": None,
            "related_pattern_id": None,
            "related_offline_event_study_id": None,
            "input_datasets_json": "[]",
            "parameters_json": "{}",
            "metrics_json": "{}",
            "lineage_json": "{}",
            "quality_status_json": "{}",
            "caveats_json": "[]",
            "outputs_json": "{}",
            "artifact_root_path": "/tmp/art",
            "manifest_path": "/tmp/manifest",
            "result_path": "/tmp/result",
            "summary_path": "/tmp/summary",
            "lineage_path": "/tmp/lineage",
            "validation_path": "/tmp/validation",
            "reproducibility_manifest_path": None,
            "generated_code_path": None,
            "created_at_ts": "2026-01-01 00:00:00",
            "updated_at_ts": "2026-01-01 00:00:00",
        },
        {
            "artifact_id": "ra-2",
            "artifact_type": "indicator_experiment",
            "name": "Artifact 2",
            "purpose": "feature build",
            "created_at": "2026-01-02 00:00:00",
            "created_by": "operator",
            "run_id": None,
            "correlation_id": "corr-legacy",
            "status": "failed",
            "sandbox_job_id": None,
            "related_experiment_id": None,
            "related_feature_id": None,
            "related_hypothesis_id": None,
            "related_pattern_id": None,
            "related_offline_event_study_id": None,
            "input_datasets_json": "[]",
            "parameters_json": "{}",
            "metrics_json": "{}",
            "lineage_json": "{}",
            "quality_status_json": "{}",
            "caveats_json": "[]",
            "outputs_json": "{}",
            "artifact_root_path": "/tmp/art2",
            "manifest_path": "/tmp/manifest2",
            "result_path": "/tmp/result2",
            "summary_path": "/tmp/summary2",
            "lineage_path": "/tmp/lineage2",
            "validation_path": "/tmp/validation2",
            "reproducibility_manifest_path": None,
            "generated_code_path": None,
            "created_at_ts": "2026-01-02 00:00:00",
            "updated_at_ts": "2026-01-02 00:00:00",
        },
    ):
        conn.execute(
            insert_sql,
            tuple(artifact_values[column] for column in columns),
        )

    run_migrations(conn=conn)

    rows = conn.execute(
        "SELECT artifact_id, status, lifecycle_state FROM research_artifact ORDER BY artifact_id"
    ).fetchall()
    assert rows == [("ra-1", "created", "RUN"), ("ra-2", "failed", "FAILED")]
