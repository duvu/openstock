from __future__ import annotations

import sqlite3
from datetime import datetime

from vnalpha.provisioning_queue._records import (
    detail,
    job_from_row,
    required_metadata,
    timestamp_ms,
)
from vnalpha.provisioning_queue._sqlite import SELECT_JOB_SQL, QueueDatabase
from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobId,
    ProvisioningJobLeaseError,
    ProvisioningJobNotFoundError,
    ProvisioningJobStatus,
    ProvisioningJobTransitionError,
    ProvisioningQueueStorageError,
    ProvisioningQueueValidationError,
)


def claim(
    database: QueueDatabase, worker_id: str, now: datetime | None
) -> ProvisioningJob | None:
    worker = required_metadata(worker_id, field_name="worker_id")
    timestamp = timestamp_ms(now)
    try:
        with database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            recover_expired(connection, timestamp, database)
            row = connection.execute(
                SELECT_JOB_SQL
                + " WHERE status = 'QUEUED' ORDER BY priority DESC, created_at_ms ASC, rowid ASC LIMIT 1"
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            job = job_from_row(row)
            connection.execute(
                "UPDATE provision_job SET status='RUNNING', stage='RUNNING', attempts=attempts+1, lease_owner=?, lease_expires_at_ms=?, lease_heartbeat_at_ms=?, updated_at_ms=? WHERE job_id=? AND status='QUEUED'",
                (
                    worker,
                    timestamp + database.configuration.lease_seconds * 1000,
                    timestamp,
                    timestamp,
                    job.job_id,
                ),
            )
            row = connection.execute(
                SELECT_JOB_SQL + " WHERE job_id = ?", (job.job_id,)
            ).fetchone()
            if row is None:
                raise ProvisioningQueueStorageError(
                    "provisioning queue lost a claimed job"
                )
            connection.commit()
            return job_from_row(row)
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not claim a job"
        ) from error


def heartbeat(
    database: QueueDatabase,
    job_id: ProvisioningJobId,
    worker_id: str,
    now: datetime | None,
) -> ProvisioningJob:
    worker = required_metadata(worker_id, field_name="worker_id")
    timestamp = timestamp_ms(now)
    try:
        with database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                "UPDATE provision_job SET lease_expires_at_ms=?, lease_heartbeat_at_ms=?, updated_at_ms=? WHERE job_id=? AND status='RUNNING' AND lease_owner=? AND lease_expires_at_ms > ? RETURNING job_id",
                (
                    timestamp + database.configuration.lease_seconds * 1000,
                    timestamp,
                    timestamp,
                    job_id,
                    worker,
                    timestamp,
                ),
            ).fetchone()
            if updated is None:
                raise_lease_error(connection, job_id)
            row = connection.execute(
                SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ProvisioningQueueStorageError(
                    "provisioning queue lost a heartbeated job"
                )
            connection.commit()
            return job_from_row(row)
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not heartbeat a job"
        ) from error


def requeue_expired(
    database: QueueDatabase, now: datetime | None
) -> tuple[ProvisioningJob, ...]:
    timestamp = timestamp_ms(now)
    try:
        with database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            recover_expired(connection, timestamp, database)
            rows = connection.execute(
                SELECT_JOB_SQL
                + " WHERE status IN ('QUEUED', 'FAILED', 'CANCELLED') ORDER BY updated_at_ms, rowid"
            ).fetchall()
            connection.commit()
            return tuple(job_from_row(row) for row in rows)
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not recover expired jobs"
        ) from error


def recover_expired(
    connection: sqlite3.Connection, timestamp: int, database: QueueDatabase
) -> None:
    rows = connection.execute(
        SELECT_JOB_SQL + " WHERE status='RUNNING' AND lease_expires_at_ms <= ?",
        (timestamp,),
    ).fetchall()
    for row in rows:
        job = job_from_row(row)
        if job.cancellation_requested:
            sql = "UPDATE provision_job SET status='CANCELLED', stage='CANCELLED', lease_owner=NULL, lease_expires_at_ms=NULL, lease_heartbeat_at_ms=NULL, updated_at_ms=? WHERE job_id=? AND status='RUNNING'"
        elif job.attempts >= database.configuration.max_attempts:
            sql = "UPDATE provision_job SET status='FAILED', stage='FAILED', error='lease retry limit exhausted', lease_owner=NULL, lease_expires_at_ms=NULL, lease_heartbeat_at_ms=NULL, updated_at_ms=? WHERE job_id=? AND status='RUNNING'"
        else:
            sql = "UPDATE provision_job SET status='QUEUED', stage='QUEUED', lease_owner=NULL, lease_expires_at_ms=NULL, lease_heartbeat_at_ms=NULL, updated_at_ms=? WHERE job_id=? AND status='RUNNING'"
        connection.execute(sql, (timestamp, job.job_id))


def terminalize(
    database: QueueDatabase,
    job_id: ProvisioningJobId,
    worker_id: str,
    status: ProvisioningJobStatus,
    value: str,
) -> ProvisioningJob:
    worker = required_metadata(worker_id, field_name="worker_id")
    timestamp = timestamp_ms(None)
    if status is ProvisioningJobStatus.SUCCEEDED:
        result, error = detail(value, field_name="result"), None
    elif status is ProvisioningJobStatus.FAILED:
        result, error = None, detail(value, field_name="error")
    elif status is ProvisioningJobStatus.CANCELLED:
        result, error = None, detail(value, field_name="cancellation reason")
    else:
        raise ProvisioningQueueValidationError(
            "only terminal queue statuses are supported"
        )
    try:
        with database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                "UPDATE provision_job SET status=?, stage=?, result=?, error=?, lease_owner=NULL, lease_expires_at_ms=NULL, lease_heartbeat_at_ms=NULL, updated_at_ms=? WHERE job_id=? AND status='RUNNING' AND lease_owner=? AND lease_expires_at_ms > ? RETURNING job_id",
                (
                    status.value,
                    status.value,
                    result,
                    error,
                    timestamp,
                    job_id,
                    worker,
                    timestamp,
                ),
            ).fetchone()
            if updated is None:
                raise_lease_error(connection, job_id)
            row = connection.execute(
                SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ProvisioningQueueStorageError(
                    "provisioning queue lost a terminal job"
                )
            connection.commit()
            return job_from_row(row)
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not terminalize a job"
        ) from error


def cancel(database: QueueDatabase, job_id: ProvisioningJobId) -> ProvisioningJob:
    timestamp = timestamp_ms(None)
    try:
        with database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ProvisioningJobNotFoundError("provisioning job not found", job_id)
            job = job_from_row(row)
            if job.status is ProvisioningJobStatus.QUEUED:
                connection.execute(
                    "UPDATE provision_job SET status='CANCELLED', stage='CANCELLED', cancellation_requested=1, updated_at_ms=? WHERE job_id=? AND status='QUEUED'",
                    (timestamp, job_id),
                )
            elif job.status is ProvisioningJobStatus.RUNNING:
                connection.execute(
                    "UPDATE provision_job SET cancellation_requested=1, updated_at_ms=? WHERE job_id=? AND status='RUNNING'",
                    (timestamp, job_id),
                )
            else:
                raise ProvisioningJobTransitionError(
                    "provisioning job is already terminal", job_id, job.status
                )
            row = connection.execute(
                SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ProvisioningQueueStorageError(
                    "provisioning queue lost a cancelled job"
                )
            connection.commit()
            return job_from_row(row)
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not cancel a job"
        ) from error


def raise_lease_error(
    connection: sqlite3.Connection, job_id: ProvisioningJobId
) -> None:
    if (
        connection.execute(
            "SELECT 1 FROM provision_job WHERE job_id = ?", (job_id,)
        ).fetchone()
        is None
    ):
        raise ProvisioningJobNotFoundError("provisioning job not found", job_id)
    raise ProvisioningJobLeaseError(
        "provisioning worker does not hold a live lease", job_id
    )
