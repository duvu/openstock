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


def test_run_migrations_adds_missing_lineage_path_column() -> None:
    conn = duckdb.connect(":memory:")
    _create_legacy_research_artifact_table_without_lineage_path(conn)

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
    conn.execute(
        insert_sql,
        (
            "ra-1",
            "indicator_experiment",
            "Artifact 1",
            "feature build",
            "2026-01-01 00:00:00",
            "operator",
            None,
            "corr-legacy",
            "created",
            None,
            None,
            None,
            None,
            None,
            None,
            "[]",
            "{}",
            "{}",
            "{}",
            "{}",
            "[]",
            "{}",
            "/tmp/art",
            "/tmp/manifest",
            "/tmp/result",
            "/tmp/summary",
            "/tmp/validation",
            None,
            None,
            "2026-01-01 00:00:00",
            "2026-01-01 00:00:00",
        ),
    )

    run_migrations(conn=conn)

    columns = {
        row[0]
        for row in conn.execute(
            "SELECT column_name "
            "FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'research_artifact'"
        ).fetchall()
    }
    assert "lineage_path" in columns
    assert "lifecycle_state" in columns

    rows = conn.execute(
        "SELECT artifact_id, COALESCE(lineage_path, ''), lifecycle_state "
        "FROM research_artifact ORDER BY artifact_id"
    ).fetchall()
    assert rows == [("ra-1", "", "RUN")]


def test_run_migrations_adds_dataset_extension_columns_to_legacy_research_experiment() -> (
    None
):
    conn = duckdb.connect(":memory:")
    _create_legacy_research_experiment_table(conn)

    columns = (
        "artifact_id",
        "definition",
        "universe",
        "start_date",
        "end_date",
        "horizon_sessions",
        "definition_json",
        "created_at_ts",
        "updated_at_ts",
    )
    insert_sql = (
        "INSERT INTO research_experiment ("
        f"{','.join(columns)}) "
        f"VALUES ({','.join(['?'] * len(columns))})"
    )
    for record_values in (
        {
            "artifact_id": "re-1",
            "definition": "relative strength 20",
            "universe": "VN30",
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "horizon_sessions": 20,
            "definition_json": '{"foo": 1}',
            "created_at_ts": "2026-01-01 00:00:00",
            "updated_at_ts": "2026-01-01 00:00:00",
        },
        {
            "artifact_id": "re-2",
            "definition": "relative strength 5",
            "universe": "VN30",
            "start_date": "2026-02-01",
            "end_date": "2026-02-05",
            "horizon_sessions": 5,
            "definition_json": '{"bar": 2}',
            "created_at_ts": "2026-02-01 00:00:00",
            "updated_at_ts": "2026-02-01 00:00:00",
        },
    ):
        conn.execute(
            insert_sql,
            tuple(record_values[column] for column in columns),
        )

    run_migrations(conn=conn)

    columns = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'research_experiment'"
        ).fetchall()
    }
    for column_name in (
        "provider_name",
        "dataset_name",
        "extension_name",
        "consumer_name",
        "dataset_version",
        "entitlement_json",
        "missingness_json",
        "transformation",
        "experiment_hash",
        "capability_status",
        "capability_payload",
    ):
        assert column_name in columns

    rows = conn.execute(
        "SELECT artifact_id, provider_name, dataset_name, extension_name, "
        "consumer_name, dataset_version, entitlement_json, missingness_json, "
        "transformation, experiment_hash, capability_status, capability_payload "
        "FROM research_experiment ORDER BY artifact_id"
    ).fetchall()
    assert rows == [
        (
            "re-1",
            None,
            None,
            None,
            None,
            None,
            "{}",
            "{}",
            None,
            None,
            "unsupported",
            "{}",
        ),
        (
            "re-2",
            None,
            None,
            None,
            None,
            None,
            "{}",
            "{}",
            None,
            None,
            "unsupported",
            "{}",
        ),
    ]
