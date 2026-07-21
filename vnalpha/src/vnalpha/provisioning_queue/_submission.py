from __future__ import annotations

import sqlite3
from datetime import datetime
from uuid import uuid4

from vnalpha.provisioning_queue._records import (
    job_from_row,
    metadata,
    timestamp_ms,
    validated_goal,
)
from vnalpha.provisioning_queue._records import (
    priority as validated_priority,
)
from vnalpha.provisioning_queue._sqlite import SELECT_JOB_SQL, QueueDatabase
from vnalpha.provisioning_queue.models import ProvisioningGoal, goal_identity, goal_type
from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobId,
    ProvisioningJobStatus,
    ProvisioningQueueStorageError,
    QueueSubmitResult,
)


def submit_or_join(
    database: QueueDatabase,
    goal: ProvisioningGoal,
    *,
    priority: int,
    origin: str | None,
    correlation_id: str | None,
    now: datetime | None,
) -> QueueSubmitResult:
    normalized_goal = validated_goal(goal)
    normalized_priority = validated_priority(priority)
    normalized_origin = metadata(origin, field_name="origin")
    normalized_correlation_id = metadata(correlation_id, field_name="correlation_id")
    timestamp = timestamp_ms(now)
    identity = goal_identity(normalized_goal)
    try:
        with database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                SELECT_JOB_SQL
                + " WHERE goal_identity = ? AND status IN ('QUEUED', 'RUNNING')",
                (identity,),
            ).fetchone()
            if row is not None:
                job = job_from_row(row)
                if job.status is ProvisioningJobStatus.QUEUED:
                    connection.execute(
                        "UPDATE provision_job SET priority = MAX(priority, ?), updated_at_ms = ? WHERE job_id = ?",
                        (normalized_priority, timestamp, job.job_id),
                    )
                    row = connection.execute(
                        SELECT_JOB_SQL + " WHERE job_id = ?", (job.job_id,)
                    ).fetchone()
                    if row is None:
                        raise ProvisioningQueueStorageError(
                            "provisioning queue lost an active job"
                        )
                    job = job_from_row(row)
                connection.commit()
                return QueueSubmitResult(job, joined_existing_job=True)
            job_id = ProvisioningJobId(uuid4().hex)
            connection.execute(
                """INSERT INTO provision_job (job_id, goal_identity, goal_type, status, priority, stage, payload_version, payload_json, origin, correlation_id, created_at_ms, updated_at_ms) VALUES (?, ?, ?, 'QUEUED', ?, 'QUEUED', ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    identity,
                    goal_type(normalized_goal).value,
                    normalized_priority,
                    normalized_goal.schema_version,
                    normalized_goal.payload_json(),
                    normalized_origin,
                    normalized_correlation_id,
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ProvisioningQueueStorageError("provisioning queue lost a new job")
            connection.commit()
            return QueueSubmitResult(job_from_row(row), joined_existing_job=False)
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not submit a job"
        ) from error


def get(database: QueueDatabase, job_id: ProvisioningJobId) -> ProvisioningJob | None:
    try:
        with database.connection() as connection:
            row = connection.execute(
                SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
            ).fetchone()
            return None if row is None else job_from_row(row)
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not read a job"
        ) from error


def list_jobs(
    database: QueueDatabase, status: ProvisioningJobStatus | None
) -> tuple[ProvisioningJob, ...]:
    try:
        with database.connection() as connection:
            sql = (
                SELECT_JOB_SQL + " ORDER BY created_at_ms, rowid"
                if status is None
                else SELECT_JOB_SQL + " WHERE status = ? ORDER BY created_at_ms, rowid"
            )
            rows = (
                connection.execute(sql)
                if status is None
                else connection.execute(sql, (status.value,))
            )
            return tuple(job_from_row(row) for row in rows.fetchall())
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not list jobs"
        ) from error
