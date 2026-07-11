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


@pytest.mark.parametrize(
    "artifact_values_sql",
    (
        """
        [
            NULL,
            {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
            {'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'}
        ]
        """,
        """
        [
            {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
            {'kind': 'summary', 'path': NULL, 'media_type': 'text/markdown'}
        ]
        """,
        """
        [
            {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
            {'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'},
            {'kind': 'chart', 'path': 'output/charts/chart.png', 'media_type': 'image/png'},
            {'kind': 'chart', 'path': 'output/charts/chart.png', 'media_type': 'image/png'}
        ]
        """,
        """
        [
            {'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'},
            {'kind': 'chart', 'path': 'output/charts/chart.png', 'media_type': 'image/png'}
        ]
        """,
        """
        [
            {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
            {'kind': 'chart', 'path': 'output/charts/chart.png', 'media_type': 'image/png'}
        ]
        """,
        """
        [
            {'kind': 'result', 'path': 'output/result.json', 'media_type': 'text/plain'},
            {'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'}
        ]
        """,
        """
        [
            {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
            {'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'},
            {'kind': 'chart', 'path': 'output/tables/chart.png', 'media_type': 'image/png'}
        ]
        """,
        """
        [
            {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
            {'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'},
            {'kind': 'table', 'path': 'output/charts/table.csv', 'media_type': 'text/csv'}
        ]
        """,
    ),
)
def test_database_rejects_invalid_typed_artifact_semantics(
    artifact_values_sql: str,
) -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        with pytest.raises(duckdb.ConstraintException):
            _insert_artifacts(conn, artifact_values_sql)


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "/output/charts/chart.png",
        r"output\charts\chart.png",
        "output/charts//chart.png",
        "output/charts/./chart.png",
        "output/charts/../chart.png",
    ),
)
def test_database_rejects_unsafe_typed_artifact_paths(unsafe_path: str) -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        with pytest.raises(duckdb.ConstraintException):
            _insert_artifacts(
                conn,
                f"""
                [
                    {{'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'}},
                    {{'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'}},
                    {{'kind': 'chart', 'path': '{unsafe_path}', 'media_type': 'image/png'}}
                ]
                """,
            )


def test_database_rejects_invalid_typed_artifact_kind() -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        with pytest.raises(duckdb.Error):
            _insert_artifacts(
                conn,
                """
                [
                    {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
                    {'kind': 'binary', 'path': 'output/charts/chart.png', 'media_type': 'image/png'}
                ]
                """,
            )


def test_database_accepts_valid_typed_artifacts() -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        _insert_artifacts(
            conn,
            """
            [
                {'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'},
                {'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'},
                {'kind': 'chart', 'path': 'output/charts/chart.png', 'media_type': 'image/png'},
                {'kind': 'table', 'path': 'output/tables/data.csv', 'media_type': 'text/csv'}
            ]
            """,
        )

        row = conn.execute("SELECT output_artifacts FROM sandbox_job").fetchone()

    assert row is not None
    assert len(row[0]) == 4
