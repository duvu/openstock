from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vnalpha.provisioning_queue._lifecycle import (
    cancel,
    claim,
    heartbeat,
    requeue_expired,
    terminalize,
)
from vnalpha.provisioning_queue._operations import get_pruned, prune_terminal
from vnalpha.provisioning_queue._records import positive
from vnalpha.provisioning_queue._sqlite import (
    DEFAULT_BUSY_TIMEOUT_MS,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_QUEUE_PATH,
    QueueConfiguration,
    QueueDatabase,
)
from vnalpha.provisioning_queue._submission import (
    find_by_identity,
    get,
    list_jobs,
    submit_or_join,
)
from vnalpha.provisioning_queue.models import ProvisioningGoal
from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobId,
    ProvisioningJobStatus,
    ProvisioningQueueHealthError,
    PrunedProvisioningJob,
    QueueCheckpointResult,
    QueueHealthReport,
    QueuePruneResult,
    QueueRuntimeSettings,
    QueueSubmitResult,
)


class ProvisioningQueue:
    """SQLite repository for finite typed provisioning jobs."""

    def __init__(
        self,
        path: Path = DEFAULT_QUEUE_PATH,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._database = QueueDatabase(
            QueueConfiguration(
                path=path,
                busy_timeout_ms=positive(
                    busy_timeout_ms, field_name="busy_timeout_ms", maximum=10_000
                ),
                lease_seconds=positive(
                    lease_seconds, field_name="lease_seconds", maximum=3_600
                ),
                max_attempts=positive(
                    max_attempts, field_name="max_attempts", maximum=10
                ),
            )
        )

    def initialize(self) -> QueueRuntimeSettings:
        return self._database.initialize()

    @property
    def path(self) -> Path:
        return self._database.configuration.path

    def runtime_settings(self) -> QueueRuntimeSettings:
        return self._database.runtime_settings()

    def health(self, *, now: datetime | None = None) -> QueueHealthReport:
        return self._database.health(now)

    def checkpoint(self, *, now: datetime | None = None) -> QueueCheckpointResult:
        self.initialize()
        return self._database.checkpoint(now)

    def prune(
        self,
        *,
        older_than_days: int,
        retained_job_ids: frozenset[ProvisioningJobId] = frozenset(),
        now: datetime | None = None,
    ) -> QueuePruneResult:
        if not 1 <= older_than_days <= 3_650:
            raise ValueError("older_than_days must be between 1 and 3650")
        self.initialize()
        return prune_terminal(
            self._database,
            older_than_days=older_than_days,
            retained_job_ids=retained_job_ids,
            now=now,
        )

    def submit_or_join(
        self,
        goal: ProvisioningGoal,
        *,
        priority: int,
        origin: str | None = None,
        correlation_id: str | None = None,
        now: datetime | None = None,
    ) -> QueueSubmitResult:
        return submit_or_join(
            self._database,
            goal,
            priority=priority,
            origin=origin,
            correlation_id=correlation_id,
            now=now,
        )

    def get(self, job_id: ProvisioningJobId) -> ProvisioningJob | None:
        return get(self._database, job_id)

    def get_pruned(self, job_id: ProvisioningJobId) -> PrunedProvisioningJob | None:
        return get_pruned(self._database, job_id)

    def find_by_identity(
        self,
        goal_identity: str,
        *,
        origin: str,
        correlation_id: str,
    ) -> ProvisioningJob | None:
        return find_by_identity(
            self._database,
            goal_identity,
            origin=origin,
            correlation_id=correlation_id,
        )

    def list(
        self, *, status: ProvisioningJobStatus | None = None
    ) -> tuple[ProvisioningJob, ...]:
        return list_jobs(self._database, status)

    def claim(
        self, worker_id: str, *, now: datetime | None = None
    ) -> ProvisioningJob | None:
        report = self.health(now=now)
        if not report.can_claim:
            raise ProvisioningQueueHealthError(
                "provisioning queue health prevents claims", report
            )
        return claim(self._database, worker_id, now)

    def heartbeat(
        self,
        job_id: ProvisioningJobId,
        worker_id: str,
        *,
        now: datetime | None = None,
    ) -> ProvisioningJob:
        return heartbeat(self._database, job_id, worker_id, now)

    def complete(
        self, job_id: ProvisioningJobId, worker_id: str, result: str
    ) -> ProvisioningJob:
        return terminalize(
            self._database, job_id, worker_id, ProvisioningJobStatus.SUCCEEDED, result
        )

    def fail(
        self,
        job_id: ProvisioningJobId,
        worker_id: str,
        error: str,
        *,
        now: datetime | None = None,
        retryable: bool = False,
    ) -> ProvisioningJob:
        return terminalize(
            self._database,
            job_id,
            worker_id,
            ProvisioningJobStatus.FAILED,
            error,
            now=now,
            retryable=retryable,
        )

    def acknowledge_cancellation(
        self, job_id: ProvisioningJobId, worker_id: str, reason: str
    ) -> ProvisioningJob:
        return terminalize(
            self._database, job_id, worker_id, ProvisioningJobStatus.CANCELLED, reason
        )

    def cancel(self, job_id: ProvisioningJobId) -> ProvisioningJob:
        return cancel(self._database, job_id)

    def requeue_expired(
        self, *, now: datetime | None = None
    ) -> tuple[ProvisioningJob, ...]:
        return requeue_expired(self._database, now)
