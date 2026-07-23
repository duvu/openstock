"""Public values and errors for the durable provisioning queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType, final

from vnalpha.provisioning_queue.models import ProvisioningGoal

ProvisioningJobId = NewType("ProvisioningJobId", str)


class ProvisioningJobStatus(StrEnum):
    """Finite lifecycle states for a durable provisioning job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@final
@dataclass(frozen=True, slots=True)
class ProvisioningJob:
    """A validated queue record returned through the repository boundary."""

    job_id: ProvisioningJobId
    goal_identity: str
    goal: ProvisioningGoal
    status: ProvisioningJobStatus
    priority: int
    stage: str
    attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    lease_heartbeat_at: datetime | None
    origin: str | None
    correlation_id: str | None
    cancellation_requested: bool
    result: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def is_terminal(self) -> bool:
        """Report whether the job has no remaining queue lifecycle work."""

        return self.status in {
            ProvisioningJobStatus.SUCCEEDED,
            ProvisioningJobStatus.FAILED,
            ProvisioningJobStatus.CANCELLED,
        }


@final
@dataclass(frozen=True, slots=True)
class QueueSubmitResult:
    """The canonical job selected by a submit-or-join request."""

    job: ProvisioningJob
    joined_existing_job: bool


@final
@dataclass(frozen=True, slots=True)
class QueueRuntimeSettings:
    """Persistent SQLite runtime settings required by the queue contract."""

    journal_mode: str
    foreign_keys_enabled: bool
    busy_timeout_ms: int
    synchronous: str
    lease_seconds: int


@final
@dataclass(frozen=True, slots=True)
class QueueHealthReport:
    """Read-only operational state used to decide whether claims are safe."""

    schema_version: int | None
    supported_schema: bool
    integrity_check: str
    integrity_ok: bool
    journal_mode: str | None
    synchronous: str | None
    busy_timeout_ms: int | None
    file_size_bytes: int
    wal_size_bytes: int
    disk_free_bytes: int | None
    disk_free_threshold_bytes: int
    disk_free_above_threshold: bool
    readable: bool
    writable: bool
    active_leases: int | None
    expired_leases: int | None
    queue_depth: int | None
    oldest_queued_age_seconds: int | None
    last_checkpoint_at: datetime | None
    last_prune_at: datetime | None
    last_migration_at: datetime | None
    detail: str | None

    @property
    def can_claim(self) -> bool:
        """Return whether the queue has passed its non-destructive claim gate."""

        return (
            self.supported_schema
            and self.integrity_ok
            and self.readable
            and self.writable
            and self.disk_free_above_threshold
        )


@final
@dataclass(frozen=True, slots=True)
class QueueCheckpointResult:
    """The bounded result of one passive SQLite WAL checkpoint."""

    busy_readers: int
    wal_frames: int
    checkpointed_frames: int
    completed_at: datetime


@final
@dataclass(frozen=True, slots=True)
class QueuePruneResult:
    """Counts from one short, evidence-aware terminal-retention batch."""

    pruned_succeeded: int
    pruned_failed: int
    pruned_cancelled: int
    retained_referenced: int
    completed_at: datetime


@final
@dataclass(frozen=True, slots=True)
class PrunedProvisioningJob:
    """Bounded history retained after terminal job detail is deliberately removed."""

    job_id: ProvisioningJobId
    final_status: ProvisioningJobStatus
    pruned_at: datetime


@final
@dataclass
class ProvisioningQueueError(Exception):
    """Base error for the queue boundary."""

    message: str

    def __str__(self) -> str:
        return self.message


@final
@dataclass
class ProvisioningQueueValidationError(ProvisioningQueueError):
    """A request cannot be represented by the finite queue contract."""


@final
@dataclass
class ProvisioningQueueStorageError(ProvisioningQueueError):
    """SQLite could not safely complete a queue operation."""


@final
@dataclass
class ProvisioningQueueHealthError(ProvisioningQueueError):
    """A non-destructive health gate prevented the next queue claim."""

    report: QueueHealthReport


@final
@dataclass
class ProvisioningJobNotFoundError(ProvisioningQueueError):
    """The requested queue job does not exist."""

    job_id: ProvisioningJobId


@final
@dataclass
class ProvisioningJobTransitionError(ProvisioningQueueError):
    """A queue lifecycle transition is not valid for the current job state."""

    job_id: ProvisioningJobId
    status: ProvisioningJobStatus


@final
@dataclass
class ProvisioningJobLeaseError(ProvisioningQueueError):
    """A worker attempted to mutate a job without its live lease."""

    job_id: ProvisioningJobId
