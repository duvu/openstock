from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Final, TypedDict

import duckdb
from pydantic import BaseModel, ConfigDict

from vnalpha.sandbox.contracts import SandboxFilesystemPolicy, SandboxOutputSchema
from vnalpha.warehouse.sandbox_schema import SANDBOX_DDL, sandbox_job_table_ddl
from vnalpha.warehouse.transaction import warehouse_transaction

_DEFAULT_SANDBOX_OUTPUT_SCHEMA: Final = SandboxOutputSchema()
_DEFAULT_SANDBOX_FILESYSTEM_POLICY: Final = SandboxFilesystemPolicy()


class _ArtifactValue(TypedDict):
    kind: str
    path: str
    media_type: str


class _LegacySandboxJobRow(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    job_id: str
    run_id: str
    correlation_id: str
    purpose: str
    code_digest: str
    status: str
    cpu_millis: int
    memory_mb: int
    timeout_seconds: int
    network_enabled: bool
    filesystem_source: str
    output_schema_json: str | None
    result_summary: str | None
    rejection_reason: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


def migrate_sandbox_contract_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Transactionally replace legacy JSON output schemas with typed artifacts."""

    has_output_artifacts = _has_sandbox_job_column(conn, "output_artifacts")
    has_output_schema = _has_sandbox_job_column(conn, "output_schema_json")
    has_legacy_paths = _has_sandbox_job_column(conn, "approved_input_paths_json")
    if has_output_artifacts and not has_output_schema and not has_legacy_paths:
        return

    has_created_at = _has_sandbox_job_column(conn, "created_at")
    has_updated_at = _has_sandbox_job_column(conn, "updated_at")
    with warehouse_transaction(conn):
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
        source = _LegacySandboxJobRow.model_validate(
            {
                "job_id": row[0],
                "run_id": row[1],
                "correlation_id": row[2],
                "purpose": row[3],
                "code_digest": row[4],
                "status": row[5],
                "cpu_millis": row[6],
                "memory_mb": row[7],
                "timeout_seconds": row[8],
                "network_enabled": row[9],
                "filesystem_source": row[10],
                "output_schema_json": row[11],
                "result_summary": row[12],
                "rejection_reason": row[13],
                "failure_reason": row[14],
                "created_at": row[15],
                "updated_at": row[16],
            }
        )
        filesystem_policy = _parse_filesystem_policy(
            source.filesystem_source, has_legacy_paths
        )
        output_schema = _parse_output_schema(
            source.output_schema_json, has_output_schema
        )
        _ = conn.execute(
            """
            INSERT INTO sandbox_job_upgrade VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                source.job_id,
                source.run_id,
                source.correlation_id,
                source.purpose,
                source.code_digest,
                source.status,
                source.cpu_millis,
                source.memory_mb,
                source.timeout_seconds,
                source.network_enabled,
                filesystem_policy.model_dump_json(),
                _typed_artifacts(output_schema),
                source.result_summary,
                source.rejection_reason,
                source.failure_reason,
                source.created_at,
                source.updated_at,
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
