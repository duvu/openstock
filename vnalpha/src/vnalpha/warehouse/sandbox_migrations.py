from __future__ import annotations

from typing import Final, TypedDict

import duckdb
from pydantic import ValidationError

from vnalpha.sandbox.contracts import SandboxFilesystemPolicy, SandboxOutputSchema
from vnalpha.warehouse.sandbox_schema import SANDBOX_DDL, sandbox_job_table_ddl

_DEFAULT_SANDBOX_OUTPUT_SCHEMA: Final = SandboxOutputSchema()
_DEFAULT_SANDBOX_FILESYSTEM_POLICY: Final = SandboxFilesystemPolicy()


class _ArtifactValue(TypedDict):
    kind: str
    path: str
    media_type: str


def migrate_sandbox_contract_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Transactionally replace legacy JSON output schemas with typed artifacts."""

    has_output_artifacts = _has_sandbox_job_column(conn, "output_artifacts")
    has_output_schema = _has_sandbox_job_column(conn, "output_schema_json")
    has_legacy_paths = _has_sandbox_job_column(conn, "approved_input_paths_json")
    if has_output_artifacts and not has_output_schema and not has_legacy_paths:
        return

    has_created_at = _has_sandbox_job_column(conn, "created_at")
    has_updated_at = _has_sandbox_job_column(conn, "updated_at")
    conn.execute("BEGIN TRANSACTION")
    try:
        _ = conn.execute(sandbox_job_table_ddl("sandbox_job_upgrade"))
        _copy_legacy_rows(
            conn,
            has_legacy_paths=has_legacy_paths,
            has_output_schema=has_output_schema,
            has_created_at=has_created_at,
            has_updated_at=has_updated_at,
        )
        _ = conn.execute("DROP TABLE sandbox_job")
        _ = conn.execute("ALTER TABLE sandbox_job_upgrade RENAME TO sandbox_job")
        _ = conn.execute(SANDBOX_DDL[-1])
    except (ValidationError, duckdb.Error):
        _ = conn.execute("ROLLBACK")
        raise
    _ = conn.execute("COMMIT")


def _copy_legacy_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    has_legacy_paths: bool,
    has_output_schema: bool,
    has_created_at: bool,
    has_updated_at: bool,
) -> None:
    filesystem_source = (
        "approved_input_paths_json" if has_legacy_paths else "filesystem_policy_json"
    )
    output_source = "output_schema_json" if has_output_schema else "NULL"
    created_at_source = "created_at" if has_created_at else "current_timestamp"
    updated_at_source = "updated_at" if has_updated_at else "current_timestamp"
    rows = conn.execute(
        f"""
        SELECT job_id, run_id, correlation_id, purpose, code_digest, status,
               cpu_millis, memory_mb, timeout_seconds, network_enabled,
               {filesystem_source}, {output_source}, result_summary,
               rejection_reason, failure_reason, {created_at_source}, {updated_at_source}
        FROM sandbox_job
        """
    ).fetchall()
    for row in rows:
        filesystem_policy = _parse_filesystem_policy(str(row[10]), has_legacy_paths)
        output_schema = _parse_output_schema(row[11], has_output_schema)
        _ = conn.execute(
            """
            INSERT INTO sandbox_job_upgrade VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
                filesystem_policy.model_dump_json(),
                _typed_artifacts(output_schema),
                row[12],
                row[13],
                row[14],
                row[15],
                row[16],
            ],
        )


def _parse_filesystem_policy(
    raw_policy: str, has_legacy_paths: bool
) -> SandboxFilesystemPolicy:
    if has_legacy_paths:
        return SandboxFilesystemPolicy.model_validate_json(
            f'{{"approved_read_paths":{raw_policy},"writable_output_directory":"output"}}'
        )
    return SandboxFilesystemPolicy.model_validate_json(raw_policy)


def _parse_output_schema(
    raw_schema: str | None, has_output_schema: bool
) -> SandboxOutputSchema:
    if has_output_schema:
        return SandboxOutputSchema.model_validate_json(str(raw_schema))
    return _DEFAULT_SANDBOX_OUTPUT_SCHEMA


def _typed_artifacts(schema: SandboxOutputSchema) -> list[_ArtifactValue]:
    return [
        {
            "kind": artifact.kind,
            "path": artifact.path,
            "media_type": artifact.media_type,
        }
        for artifact in schema.artifacts
    ]


def _has_sandbox_job_column(conn: duckdb.DuckDBPyConnection, column_name: str) -> bool:
    return (
        conn.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'sandbox_job' AND column_name = ?
            """,
            [column_name],
        ).fetchone()
        is not None
    )
