from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Final

from vnalpha.provisioning_queue.models import (
    InvalidProvisioningGoalError,
    ProvisioningGoal,
    parse_goal_payload,
)
from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobId,
    ProvisioningJobStatus,
    ProvisioningQueueStorageError,
    ProvisioningQueueValidationError,
)

MAX_QUEUE_DETAIL_BYTES: Final = 2_048
MAX_QUEUE_METADATA_BYTES: Final = 128
MAX_QUEUE_PRIORITY: Final = 1_000


def job_from_row(row: sqlite3.Row) -> ProvisioningJob:
    try:
        return ProvisioningJob(
            job_id=ProvisioningJobId(str(row["job_id"])),
            goal_identity=str(row["goal_identity"]),
            goal=parse_goal_payload(str(row["payload_json"])),
            status=ProvisioningJobStatus(str(row["status"])),
            priority=int(row["priority"]),
            stage=str(row["stage"]),
            attempts=int(row["attempts"]),
            lease_owner=optional_text(row["lease_owner"]),
            lease_expires_at=optional_datetime(row["lease_expires_at_ms"]),
            lease_heartbeat_at=optional_datetime(row["lease_heartbeat_at_ms"]),
            origin=optional_text(row["origin"]),
            correlation_id=optional_text(row["correlation_id"]),
            cancellation_requested=bool(row["cancellation_requested"]),
            result=optional_text(row["result"]),
            error=optional_text(row["error"]),
            created_at=datetime_from_timestamp(int(row["created_at_ms"])),
            updated_at=datetime_from_timestamp(int(row["updated_at_ms"])),
        )
    except (KeyError, TypeError, ValueError, InvalidProvisioningGoalError) as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue contains invalid data"
        ) from error


def validated_goal(goal: ProvisioningGoal) -> ProvisioningGoal:
    try:
        return parse_goal_payload(goal.payload_json())
    except (AttributeError, InvalidProvisioningGoalError):
        raise ProvisioningQueueValidationError("invalid provisioning goal") from None


def timestamp_ms(now: datetime | None) -> int:
    resolved = datetime.now(UTC) if now is None else now.astimezone(UTC)
    return int(resolved.timestamp() * 1_000)


def datetime_from_timestamp(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1_000, UTC)


def optional_datetime(value: int | None) -> datetime | None:
    return None if value is None else datetime_from_timestamp(value)


def optional_text(value: str | None) -> str | None:
    return None if value is None else str(value)


def positive(value: int, *, field_name: str, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= maximum
    ):
        raise ProvisioningQueueValidationError(f"{field_name} must be bounded")
    return value


def priority(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= MAX_QUEUE_PRIORITY
    ):
        raise ProvisioningQueueValidationError("priority must be bounded")
    return value


def metadata(value: str | None, *, field_name: str) -> str | None:
    return None if value is None else required_metadata(value, field_name=field_name)


def required_metadata(value: str, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode()) > MAX_QUEUE_METADATA_BYTES
        or any(character in value for character in "\r\n\x00")
    ):
        raise ProvisioningQueueValidationError(f"{field_name} must be bounded metadata")
    return value


def detail(value: str, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode()) > MAX_QUEUE_DETAIL_BYTES
    ):
        raise ProvisioningQueueValidationError(f"{field_name} must be bounded")
    return value
