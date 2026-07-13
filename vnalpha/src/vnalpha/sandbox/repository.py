"""DuckDB persistence for safe, durable sandbox-job metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TypedDict, assert_never, final

import duckdb
from pydantic import BaseModel, ConfigDict

from vnalpha.sandbox.contracts import (
    MAX_APPROVED_READ_PATHS_JSON_LENGTH,
    SandboxFilesystemPolicy,
    SandboxJobValidationError,
    SandboxOutputSchema,
)
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobDetail,
    SandboxJobId,
    SandboxJobNotFoundError,
    SandboxJobStatus,
    SandboxJobTransitionError,
    SandboxRunId,
    parse_sandbox_job_detail,
    validate_sandbox_job,
)


@final
@dataclass(frozen=True, slots=True)
class SandboxJobRecord:
    """The safe metadata retained after a job request is accepted."""

    job_id: SandboxJobId
    run_id: SandboxRunId
    correlation_id: SandboxCorrelationId
    purpose: str
    code_digest: str
    status: SandboxJobStatus
    filesystem_policy: SandboxFilesystemPolicy
    output_schema: SandboxOutputSchema
    result_summary: str | None
    rejection_reason: str | None
    failure_reason: str | None


class _ArtifactValue(TypedDict):
    kind: str
    path: str
    media_type: str


@final
class SandboxJobRepository:
    """Persist sandbox metadata through the caller-owned DuckDB connection."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn: duckdb.DuckDBPyConnection = conn

    def create(self, job: SandboxJob) -> None:
        """Insert a queued job without retaining its code contents."""

        validate_sandbox_job(job)
        filesystem_policy_json = job.filesystem_policy.model_dump_json()
        if len(filesystem_policy_json) > MAX_APPROVED_READ_PATHS_JSON_LENGTH:
            raise SandboxJobValidationError(
                "filesystem_policy", "serialized value too large"
            )
        _ = self._conn.execute(
            """
            INSERT INTO sandbox_job (
                job_id, run_id, correlation_id, purpose, code_digest, status,
                cpu_millis, memory_mb, timeout_seconds, network_enabled,
                filesystem_policy_json, output_artifacts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                job.job_id,
                job.run_id,
                job.correlation_id,
                job.purpose,
                job.code_digest,
                job.status.value,
                job.resource_limits.cpu_millis,
                job.resource_limits.memory_mb,
                job.resource_limits.timeout_seconds,
                job.network_enabled,
                filesystem_policy_json,
                _typed_artifacts(job.output_schema),
            ],
        )

    def get(self, job_id: SandboxJobId) -> SandboxJobRecord | None:
        """Return one persisted sandbox job by its branded identifier."""

        row = self._conn.execute(
            _SELECT_SANDBOX_JOB_SQL + " WHERE job_id = ?", [job_id]
        ).fetchone()
        return None if row is None else _record_from_row(row)

    def list(self) -> tuple[SandboxJobRecord, ...]:
        """List durable sandbox jobs ordered by insertion time."""

        rows = self._conn.execute(
            _SELECT_SANDBOX_JOB_SQL + " ORDER BY created_at, job_id"
        ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def list_by_correlation(
        self, correlation_id: SandboxCorrelationId
    ) -> tuple[SandboxJobRecord, ...]:
        """List all jobs associated with one correlation identifier."""

        rows = self._conn.execute(
            _SELECT_SANDBOX_JOB_SQL
            + " WHERE correlation_id = ? ORDER BY created_at, job_id",
            [correlation_id],
        ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def claim_for_validation(self, job_id: SandboxJobId) -> None:
        """Atomically consume a queued job before guard or Docker work begins."""

        row = self._conn.execute(
            _CLAIM_FOR_VALIDATION_SQL,
            [SandboxJobStatus.VALIDATING.value, job_id],
        ).fetchone()
        if row is not None:
            return
        current = self.get(job_id)
        if current is None:
            raise SandboxJobNotFoundError(job_id)
        raise SandboxJobTransitionError(job_id, current.status)

    def mark_succeeded(self, job_id: SandboxJobId, result_summary: str) -> None:
        """Persist a bounded successful result summary."""

        self._update_terminal(
            job_id, SandboxJobStatus.SUCCEEDED, parse_sandbox_job_detail(result_summary)
        )

    def mark_rejected(self, job_id: SandboxJobId, reason: str) -> None:
        """Persist the explicit rejection reason for a job."""

        self._update_terminal(
            job_id, SandboxJobStatus.REJECTED, parse_sandbox_job_detail(reason)
        )

    def mark_failed(self, job_id: SandboxJobId, reason: str) -> None:
        """Persist the bounded failure reason for a job."""

        self._update_terminal(
            job_id, SandboxJobStatus.FAILED, parse_sandbox_job_detail(reason)
        )

    def _update_terminal(
        self, job_id: SandboxJobId, status: SandboxJobStatus, detail: SandboxJobDetail
    ) -> None:
        match status:
            case SandboxJobStatus.SUCCEEDED:
                row = self._conn.execute(
                    _SUCCEEDED_UPDATE_SQL, [status.value, detail, job_id]
                ).fetchone()
            case SandboxJobStatus.REJECTED:
                row = self._conn.execute(
                    _REJECTED_UPDATE_SQL, [status.value, detail, job_id]
                ).fetchone()
            case SandboxJobStatus.FAILED:
                row = self._conn.execute(
                    _FAILED_UPDATE_SQL, [status.value, detail, job_id]
                ).fetchone()
            case (
                SandboxJobStatus.QUEUED
                | SandboxJobStatus.VALIDATING
                | SandboxJobStatus.RUNNING
                | SandboxJobStatus.CANCELLED
            ):
                raise SandboxJobTransitionError(job_id, status)
            case _ as unreachable:
                assert_never(unreachable)
        if row is not None:
            return
        current = self.get(job_id)
        if current is None:
            raise SandboxJobNotFoundError(job_id)
        raise SandboxJobTransitionError(job_id, current.status)


_SELECT_SANDBOX_JOB_SQL = """
SELECT job_id, run_id, correlation_id, purpose, code_digest, status,
       filesystem_policy_json,
       CAST(json_object('artifacts', output_artifacts) AS VARCHAR) AS output_schema_json,
       result_summary, rejection_reason, failure_reason
FROM sandbox_job
"""

_TERMINAL_SOURCE_STATE_SQL = "status IN ('queued', 'validating', 'running')"
_CLAIM_FOR_VALIDATION_SQL = """
UPDATE sandbox_job SET status = ?, updated_at = current_timestamp
WHERE job_id = ? AND status = 'queued'
RETURNING job_id
"""
_SUCCEEDED_UPDATE_SQL = f"""
UPDATE sandbox_job SET status = ?, result_summary = ?, updated_at = current_timestamp
WHERE job_id = ? AND {_TERMINAL_SOURCE_STATE_SQL}
RETURNING job_id
"""
_REJECTED_UPDATE_SQL = f"""
UPDATE sandbox_job SET status = ?, rejection_reason = ?, updated_at = current_timestamp
WHERE job_id = ? AND {_TERMINAL_SOURCE_STATE_SQL}
RETURNING job_id
"""
_FAILED_UPDATE_SQL = f"""
UPDATE sandbox_job SET status = ?, failure_reason = ?, updated_at = current_timestamp
WHERE job_id = ? AND {_TERMINAL_SOURCE_STATE_SQL}
RETURNING job_id
"""


class _SandboxJobRecordPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    run_id: str
    correlation_id: str
    purpose: str
    code_digest: str
    status: SandboxJobStatus
    filesystem_policy_json: str
    output_schema_json: str
    result_summary: str | None
    rejection_reason: str | None
    failure_reason: str | None

    def into_record(self) -> SandboxJobRecord:
        return SandboxJobRecord(
            job_id=SandboxJobId(self.job_id),
            run_id=SandboxRunId(self.run_id),
            correlation_id=SandboxCorrelationId(self.correlation_id),
            purpose=self.purpose,
            code_digest=self.code_digest,
            status=self.status,
            filesystem_policy=SandboxFilesystemPolicy.model_validate_json(
                self.filesystem_policy_json
            ),
            output_schema=SandboxOutputSchema.model_validate_json(
                self.output_schema_json
            ),
            result_summary=self.result_summary,
            rejection_reason=self.rejection_reason,
            failure_reason=self.failure_reason,
        )


def _record_from_row(row: tuple[str | None, ...]) -> SandboxJobRecord:
    return _SandboxJobRecordPayload.model_validate(
        {
            "job_id": row[0],
            "run_id": row[1],
            "correlation_id": row[2],
            "purpose": row[3],
            "code_digest": row[4],
            "status": row[5],
            "filesystem_policy_json": row[6],
            "output_schema_json": row[7],
            "result_summary": row[8],
            "rejection_reason": row[9],
            "failure_reason": row[10],
        }
    ).into_record()


def _typed_artifacts(schema: SandboxOutputSchema) -> list[_ArtifactValue]:
    return [
        {
            "kind": artifact.kind,
            "path": artifact.path,
            "media_type": artifact.media_type,
        }
        for artifact in schema.artifacts
    ]
