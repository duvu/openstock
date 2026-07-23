from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Final

from vnalpha.provisioning_queue._records import datetime_from_timestamp, timestamp_ms
from vnalpha.provisioning_queue._sqlite import QueueDatabase
from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJobId,
    ProvisioningJobStatus,
    ProvisioningQueueStorageError,
    PrunedProvisioningJob,
    QueuePruneResult,
)

MAX_PRUNE_BATCH_SIZE: Final = 100


def get_pruned(
    database: QueueDatabase, job_id: ProvisioningJobId
) -> PrunedProvisioningJob | None:
    try:
        with database.connection() as connection:
            row = connection.execute(
                "SELECT final_status, pruned_at_ms FROM pruned_provision_job "
                "WHERE job_id = ?",
                (job_id,),
            ).fetchone()
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not read pruned job history"
        ) from error
    if row is None:
        return None
    return PrunedProvisioningJob(
        job_id=job_id,
        final_status=ProvisioningJobStatus(str(row[0])),
        pruned_at=datetime_from_timestamp(int(row[1])),
    )


def prune_terminal(
    database: QueueDatabase,
    *,
    older_than_days: int,
    retained_job_ids: frozenset[ProvisioningJobId],
    now: datetime | None,
) -> QueuePruneResult:
    completed_at = datetime.now(UTC) if now is None else now.astimezone(UTC)
    cutoff = timestamp_ms(completed_at - timedelta(days=older_than_days))
    pruned_counts = {
        ProvisioningJobStatus.SUCCEEDED: 0,
        ProvisioningJobStatus.FAILED: 0,
        ProvisioningJobStatus.CANCELLED: 0,
    }
    retained_referenced = 0
    try:
        with database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT job_id, status FROM provision_job "
                "WHERE status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') "
                "AND updated_at_ms < ? ORDER BY updated_at_ms ASC LIMIT ?",
                (cutoff, MAX_PRUNE_BATCH_SIZE),
            ).fetchall()
            for row in rows:
                job_id = ProvisioningJobId(str(row[0]))
                status = ProvisioningJobStatus(str(row[1]))
                if job_id in retained_job_ids:
                    retained_referenced += 1
                    continue
                connection.execute(
                    "INSERT INTO pruned_provision_job (job_id, final_status, pruned_at_ms) "
                    "VALUES (?, ?, ?)",
                    (job_id, status.value, timestamp_ms(completed_at)),
                )
                connection.execute(
                    "DELETE FROM provision_job WHERE job_id = ? "
                    "AND status IN ('SUCCEEDED', 'FAILED', 'CANCELLED')",
                    (job_id,),
                )
                pruned_counts[status] += 1
            database._set_metadata(
                connection,
                "last_prune_at_ms",
                timestamp_ms(completed_at),
            )
            connection.commit()
    except sqlite3.Error as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue could not prune terminal jobs"
        ) from error
    return QueuePruneResult(
        pruned_succeeded=pruned_counts[ProvisioningJobStatus.SUCCEEDED],
        pruned_failed=pruned_counts[ProvisioningJobStatus.FAILED],
        pruned_cancelled=pruned_counts[ProvisioningJobStatus.CANCELLED],
        retained_referenced=retained_referenced,
        completed_at=completed_at,
    )
