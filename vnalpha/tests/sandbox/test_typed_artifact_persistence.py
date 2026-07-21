from __future__ import annotations

import duckdb
import pytest

from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

_FILESYSTEM_POLICY_JSON = (
    '{"approved_read_paths":[],"writable_output_directory":"output"}'
)


def _insert_artifacts(
    conn: duckdb.DuckDBPyConnection, artifact_values_sql: str
) -> None:
    _ = conn.execute(
        f"""
        INSERT INTO sandbox_job (
            job_id, run_id, correlation_id, purpose, code_digest, status,
            cpu_millis, memory_mb, timeout_seconds, network_enabled,
            filesystem_policy_json, output_artifacts
        ) VALUES (
            'typed-job', 'typed-run', 'typed-correlation', 'evaluate', 'digest',
            'queued', 1, 16, 1, FALSE, '{_FILESYSTEM_POLICY_JSON}',
            {artifact_values_sql}
        )
        """
    )


def test_database_rejects_chart_outside_canonical_directory() -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        with pytest.raises(duckdb.ConstraintException):
            _insert_artifacts(
                conn,
                """
                [
                    {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
                    {'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'},
                    {'kind': 'chart', 'path': 'output/chart.png', 'media_type': 'image/png'}
                ]
                """,
            )
