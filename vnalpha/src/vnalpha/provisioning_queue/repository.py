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
        self, job_id: ProvisioningJobId, worker_id: str, error: str
    ) -> ProvisioningJob:
        return terminalize(
            self._database, job_id, worker_id, ProvisioningJobStatus.FAILED, error
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
