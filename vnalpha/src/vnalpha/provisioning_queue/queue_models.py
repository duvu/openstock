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


@final
@dataclass(frozen=True, slots=True)
class ProvisioningQueueError(Exception):
    """Base error for the queue boundary."""

    message: str

    def __str__(self) -> str:
        return self.message


@final
@dataclass(frozen=True, slots=True)
class ProvisioningQueueValidationError(ProvisioningQueueError):
    """A request cannot be represented by the finite queue contract."""


@final
@dataclass(frozen=True, slots=True)
class ProvisioningQueueStorageError(ProvisioningQueueError):
    """SQLite could not safely complete a queue operation."""


@final
@dataclass(frozen=True, slots=True)
class ProvisioningJobNotFoundError(ProvisioningQueueError):
    """The requested queue job does not exist."""

    job_id: ProvisioningJobId


@final
@dataclass(frozen=True, slots=True)
class ProvisioningJobTransitionError(ProvisioningQueueError):
    """A queue lifecycle transition is not valid for the current job state."""

    job_id: ProvisioningJobId
    status: ProvisioningJobStatus


@final
@dataclass(frozen=True, slots=True)
class ProvisioningJobLeaseError(ProvisioningQueueError):
    """A worker attempted to mutate a job without its live lease."""

    job_id: ProvisioningJobId
