from __future__ import annotations

import duckdb
import pytest
from pydantic import ValidationError

from vnalpha.sandbox.contracts import SandboxOutputSchema
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


def _insert_sandbox_row(
    conn: duckdb.DuckDBPyConnection,
    filesystem_policy_json: str | None,
) -> None:
    _ = conn.execute(
        """
        INSERT INTO sandbox_job (
            job_id, run_id, correlation_id, purpose, code_digest, status,
            cpu_millis, memory_mb, timeout_seconds, network_enabled,
            filesystem_policy_json, output_artifacts
        ) VALUES ('job-001', 'run-001', 'contracts-42', 'evaluate', 'digest',
                  'queued', 1, 16, 1, FALSE, ?, ?)
        """,
        [
            filesystem_policy_json,
            [
                {
                    "kind": "result",
                    "path": "output/result.json",
                    "media_type": "application/json",
                },
                {
                    "kind": "summary",
                    "path": "output/summary.md",
                    "media_type": "text/markdown",
                },
            ],
        ],
    )


def test_output_schema_rejects_more_than_32_artifacts() -> None:
    artifacts = (
        {
            "kind": "result",
            "path": "output/result.json",
            "media_type": "application/json",
        },
        {
            "kind": "summary",
            "path": "output/summary.md",
            "media_type": "text/markdown",
        },
        *tuple(
            {
                "kind": "chart",
                "path": f"output/charts/chart-{index}.png",
                "media_type": "image/png",
            }
            for index in range(31)
        ),
    )

    with pytest.raises(ValidationError):
        _ = SandboxOutputSchema.model_validate({"artifacts": artifacts})


@pytest.mark.parametrize(
    "filesystem_policy_json",
    (
        None,
        "not-json",
        "x" * 4_097,
        '{"approved_read_paths":[],"writable_output_directory":"other"}',
        '{"approved_read_paths":["../secret"],"writable_output_directory":"output"}',
    ),
)
def test_sandbox_job_database_rejects_invalid_filesystem_policy_json(
    filesystem_policy_json: str | None,
) -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        with pytest.raises(duckdb.ConstraintException):
            _insert_sandbox_row(conn, filesystem_policy_json)


def test_legacy_migration_rebuilds_contract_columns_idempotently() -> None:
    with in_memory_connection() as conn:
        _ = conn.execute(
            """
            CREATE TABLE sandbox_job (
                job_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                correlation_id VARCHAR NOT NULL,
                purpose VARCHAR NOT NULL,
                code_digest VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                cpu_millis INTEGER NOT NULL,
                memory_mb INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                network_enabled BOOLEAN NOT NULL,
                approved_input_paths_json VARCHAR NOT NULL,
                result_summary VARCHAR,
                rejection_reason VARCHAR,
                failure_reason VARCHAR
            )
            """
        )
        _ = conn.execute(
            """
            INSERT INTO sandbox_job VALUES (
                'legacy-job', 'legacy-run', 'legacy-correlation', 'evaluate', 'digest',
                'queued', 1, 16, 1, FALSE, '["inputs/legacy.json"]', NULL, NULL, NULL
            )
            """
        )

        run_migrations(conn=conn)
        run_migrations(conn=conn)
        columns = conn.execute(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sandbox_job'
            """
        ).fetchall()
        row = conn.execute(
            """
            SELECT filesystem_policy_json, output_artifacts
            FROM sandbox_job WHERE job_id = 'legacy-job'
            """
        ).fetchone()

    assert row is not None
    assert "inputs/legacy.json" in row[0]
    assert row[1][0]["path"] == "output/result.json"
    assert ("approved_input_paths_json", "YES") not in columns
    assert ("filesystem_policy_json", "NO") in columns
    assert ("output_artifacts", "NO") in columns
    assert ("output_schema_json", "YES") not in columns


def test_legacy_migration_rejects_traversal_path_before_rebuilding() -> None:
    with in_memory_connection() as conn:
        _ = conn.execute(
            """
            CREATE TABLE sandbox_job (
                job_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                correlation_id VARCHAR NOT NULL,
                purpose VARCHAR NOT NULL,
                code_digest VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                cpu_millis INTEGER NOT NULL,
                memory_mb INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                network_enabled BOOLEAN NOT NULL,
                approved_input_paths_json VARCHAR NOT NULL,
                result_summary VARCHAR,
                rejection_reason VARCHAR,
                failure_reason VARCHAR
            )
            """
        )
        _ = conn.execute(
            """
            INSERT INTO sandbox_job VALUES (
                'legacy-job', 'legacy-run', 'legacy-correlation', 'evaluate', 'digest',
                'queued', 1, 16, 1, FALSE, '["../secret"]', NULL, NULL, NULL
            )
            """
        )

        with pytest.raises(ValueError):
            run_migrations(conn=conn)

        columns = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'sandbox_job'
            """
        ).fetchall()

    assert ("approved_input_paths_json",) in columns


def test_legacy_migration_rejects_out_of_scope_optional_artifact() -> None:
    with in_memory_connection() as conn:
        _ = conn.execute(
            """
            CREATE TABLE sandbox_job (
                job_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                correlation_id VARCHAR NOT NULL,
                purpose VARCHAR NOT NULL,
                code_digest VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                cpu_millis INTEGER NOT NULL,
                memory_mb INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                network_enabled BOOLEAN NOT NULL,
                approved_input_paths_json VARCHAR NOT NULL,
                output_schema_json VARCHAR,
                result_summary VARCHAR,
                rejection_reason VARCHAR,
                failure_reason VARCHAR
            )
            """
        )
        _ = conn.execute(
            """
            INSERT INTO sandbox_job VALUES (
                'legacy-job', 'legacy-run', 'legacy-correlation', 'evaluate', 'digest',
                'queued', 1, 16, 1, FALSE, '[]',
                '{"artifacts":[{"kind":"result","path":"output/result.json","media_type":"application/json"},{"kind":"summary","path":"output/summary.md","media_type":"text/markdown"},{"kind":"chart","path":"output/chart.png","media_type":"image/png"}]}',
                NULL, NULL, NULL
            )
            """
        )

        with pytest.raises(ValueError):
            run_migrations(conn=conn)


def test_legacy_json_output_schema_migrates_to_typed_artifacts() -> None:
    legacy_schema_json = """
    {"artifacts":[
        {"kind":"result","path":"output/result.json","media_type":"application/json"},
        {"kind":"summary","path":"output/summary.md","media_type":"text/markdown"},
        {"kind":"chart","path":"output/charts/chart.png","media_type":"image/png"}
    ]}
    """
    with in_memory_connection() as conn:
        _ = conn.execute(
            """
            CREATE TABLE sandbox_job (
                job_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                correlation_id VARCHAR NOT NULL,
                purpose VARCHAR NOT NULL,
                code_digest VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                cpu_millis INTEGER NOT NULL,
                memory_mb INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                network_enabled BOOLEAN NOT NULL,
                approved_input_paths_json VARCHAR NOT NULL,
                output_schema_json VARCHAR NOT NULL,
                result_summary VARCHAR,
                rejection_reason VARCHAR,
                failure_reason VARCHAR
            )
            """
        )
        _ = conn.execute(
            """
            INSERT INTO sandbox_job VALUES (
                'legacy-job', 'legacy-run', 'legacy-correlation', 'evaluate', 'digest',
                'queued', 1, 16, 1, FALSE, '[]', ?, NULL, NULL, NULL
            )
            """,
            [legacy_schema_json],
        )

        run_migrations(conn=conn)
        row = conn.execute(
            "SELECT output_artifacts FROM sandbox_job WHERE job_id = 'legacy-job'"
        ).fetchone()

    assert row is not None
    assert row[0][2]["path"] == "output/charts/chart.png"
