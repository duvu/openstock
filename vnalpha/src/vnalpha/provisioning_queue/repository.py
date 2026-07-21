"""SQLite persistence for finite, durable provisioning jobs."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Iterator
from uuid import uuid4

from vnalpha.provisioning_queue.models import (
    InvalidProvisioningGoalError,
    ProvisioningGoal,
    goal_identity,
    goal_type,
    parse_goal_payload,
)
from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobId,
    ProvisioningJobLeaseError,
    ProvisioningJobNotFoundError,
    ProvisioningJobStatus,
    ProvisioningJobTransitionError,
    ProvisioningQueueStorageError,
    ProvisioningQueueValidationError,
    QueueRuntimeSettings,
    QueueSubmitResult,
)

DEFAULT_QUEUE_PATH: Final = Path("/var/lib/openstock/queue/provisioning.sqlite3")
DEFAULT_BUSY_TIMEOUT_MS: Final = 1_000
DEFAULT_LEASE_SECONDS: Final = 60
DEFAULT_MAX_ATTEMPTS: Final = 3
MAX_QUEUE_DETAIL_BYTES: Final = 2_048
MAX_QUEUE_METADATA_BYTES: Final = 128
MAX_QUEUE_PRIORITY: Final = 1_000
_SCHEMA_VERSION: Final = 1
_TERMINAL_STATUSES: Final = (
    ProvisioningJobStatus.SUCCEEDED,
    ProvisioningJobStatus.FAILED,
    ProvisioningJobStatus.CANCELLED,
)
_ACTIVE_STATUSES: Final = (
    ProvisioningJobStatus.QUEUED,
    ProvisioningJobStatus.RUNNING,
)


class ProvisioningQueue:
    """Persist and coordinate typed provisioning goals without opening DuckDB."""

    def __init__(
        self,
        path: Path = DEFAULT_QUEUE_PATH,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._path = path
        self._busy_timeout_ms = _validated_positive(
            busy_timeout_ms, field_name="busy_timeout_ms", maximum=10_000
        )
        self._lease_seconds = _validated_positive(
            lease_seconds, field_name="lease_seconds", maximum=3_600
        )
        self._max_attempts = _validated_positive(
            max_attempts, field_name="max_attempts", maximum=10
        )

    def initialize(self) -> QueueRuntimeSettings:
        """Create or migrate the one-table queue schema without touching DuckDB."""

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as connection:
                schema_version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                match schema_version:
                    case 0:
                        connection.executescript(_CREATE_SCHEMA_SQL)
                        connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                    case 1:
                        pass
                    case _:
                        raise ProvisioningQueueStorageError(
                            "unsupported provisioning queue schema version"
                        )
                return self._runtime_settings(connection)
        except (OSError, sqlite3.Error) as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue storage is unavailable"
            ) from error

    def runtime_settings(self) -> QueueRuntimeSettings:
        """Return the effective explicit SQLite settings for this queue file."""

        try:
            with self._connection() as connection:
                return self._runtime_settings(connection)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue storage is unavailable"
            ) from error

    def submit_or_join(
        self,
        goal: ProvisioningGoal,
        *,
        priority: int,
        origin: str | None = None,
        correlation_id: str | None = None,
        now: datetime | None = None,
    ) -> QueueSubmitResult:
        """Persist a typed goal or join its equivalent active job atomically."""

        normalized_goal = _validated_goal(goal)
        normalized_priority = _validated_priority(priority)
        normalized_origin = _validated_metadata(origin, field_name="origin")
        normalized_correlation = _validated_metadata(
            correlation_id, field_name="correlation_id"
        )
        timestamp = _timestamp_ms(now)
        identity = goal_identity(normalized_goal)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    _SELECT_JOB_SQL
                    + " WHERE goal_identity = ? AND status IN ('QUEUED', 'RUNNING')",
                    (identity,),
                ).fetchone()
                if existing is not None:
                    existing_job = _job_from_row(existing)
                    if existing_job.status is ProvisioningJobStatus.QUEUED:
                        connection.execute(
                            """
                            UPDATE provision_job
                            SET priority = MAX(priority, ?), updated_at_ms = ?
                            WHERE job_id = ?
                            """,
                            (normalized_priority, timestamp, existing_job.job_id),
                        )
                        existing = connection.execute(
                            _SELECT_JOB_SQL + " WHERE job_id = ?",
                            (existing_job.job_id,),
                        ).fetchone()
                        if existing is None:
                            raise ProvisioningQueueStorageError(
                                "provisioning queue lost an active job"
                            )
                        existing_job = _job_from_row(existing)
                    connection.commit()
                    return QueueSubmitResult(existing_job, joined_existing_job=True)

                job_id = ProvisioningJobId(uuid4().hex)
                connection.execute(
                    _INSERT_JOB_SQL,
                    (
                        job_id,
                        identity,
                        goal_type(normalized_goal).value,
                        ProvisioningJobStatus.QUEUED.value,
                        normalized_priority,
                        ProvisioningJobStatus.QUEUED.value,
                        normalized_goal.schema_version,
                        normalized_goal.payload_json(),
                        normalized_origin,
                        normalized_correlation,
                        timestamp,
                        timestamp,
                    ),
                )
                row = connection.execute(
                    _SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
                ).fetchone()
                if row is None:
                    raise ProvisioningQueueStorageError(
                        "provisioning queue lost a new job"
                    )
                connection.commit()
                return QueueSubmitResult(_job_from_row(row), joined_existing_job=False)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue could not submit a job"
            ) from error

    def get(self, job_id: ProvisioningJobId) -> ProvisioningJob | None:
        """Return one durable job without acquiring a write transaction."""

        try:
            with self._connection() as connection:
                row = connection.execute(
                    _SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
                ).fetchone()
                return None if row is None else _job_from_row(row)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue could not read a job"
            ) from error

    def list(
        self, *, status: ProvisioningJobStatus | None = None
    ) -> tuple[ProvisioningJob, ...]:
        """List durable jobs in creation order, optionally for one status."""

        try:
            with self._connection() as connection:
                if status is None:
                    rows = connection.execute(
                        _SELECT_JOB_SQL + " ORDER BY created_at_ms, rowid"
                    ).fetchall()
                else:
                    rows = connection.execute(
                        _SELECT_JOB_SQL
                        + " WHERE status = ? ORDER BY created_at_ms, rowid",
                        (status.value,),
                    ).fetchall()
                return tuple(_job_from_row(row) for row in rows)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue could not list jobs"
            ) from error

    def claim(
        self, worker_id: str, *, now: datetime | None = None
    ) -> ProvisioningJob | None:
        """Atomically recover expired work and claim the highest-priority queued job."""

        normalized_worker_id = _required_metadata(worker_id, field_name="worker_id")
        timestamp = _timestamp_ms(now)
        lease_expiry = timestamp + self._lease_seconds * 1_000
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._requeue_expired(connection, timestamp)
                row = connection.execute(
                    _SELECT_JOB_SQL
                    + " WHERE status = 'QUEUED' ORDER BY priority DESC, created_at_ms ASC, rowid ASC LIMIT 1"
                ).fetchone()
                if row is None:
                    connection.commit()
                    return None
                queued_job = _job_from_row(row)
                connection.execute(
                    """
                    UPDATE provision_job
                    SET status = 'RUNNING', stage = 'RUNNING', attempts = attempts + 1,
                        lease_owner = ?, lease_expires_at_ms = ?, lease_heartbeat_at_ms = ?,
                        updated_at_ms = ?
                    WHERE job_id = ? AND status = 'QUEUED'
                    """,
                    (
                        normalized_worker_id,
                        lease_expiry,
                        timestamp,
                        timestamp,
                        queued_job.job_id,
                    ),
                )
                claimed = connection.execute(
                    _SELECT_JOB_SQL + " WHERE job_id = ?", (queued_job.job_id,)
                ).fetchone()
                if claimed is None:
                    raise ProvisioningQueueStorageError(
                        "provisioning queue lost a claimed job"
                    )
                connection.commit()
                return _job_from_row(claimed)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue could not claim a job"
            ) from error

    def heartbeat(
        self,
        job_id: ProvisioningJobId,
        worker_id: str,
        *,
        now: datetime | None = None,
    ) -> ProvisioningJob:
        """Extend the live lease held by one worker at a safe stage boundary."""

        normalized_worker_id = _required_metadata(worker_id, field_name="worker_id")
        timestamp = _timestamp_ms(now)
        expiry = timestamp + self._lease_seconds * 1_000
        return self._update_live_lease(
            job_id, normalized_worker_id, timestamp=timestamp, expiry=expiry
        )

    def complete(
        self, job_id: ProvisioningJobId, worker_id: str, result: str
    ) -> ProvisioningJob:
        """Persist a bounded successful terminal result for the lease holder."""

        return self._terminalize(
            job_id,
            worker_id,
            status=ProvisioningJobStatus.SUCCEEDED,
            detail=_validated_detail(result, field_name="result"),
        )

    def fail(
        self, job_id: ProvisioningJobId, worker_id: str, error: str
    ) -> ProvisioningJob:
        """Persist a bounded failed terminal result for the lease holder."""

        return self._terminalize(
            job_id,
            worker_id,
            status=ProvisioningJobStatus.FAILED,
            detail=_validated_detail(error, field_name="error"),
        )

    def cancel(self, job_id: ProvisioningJobId) -> ProvisioningJob:
        """Cancel queued work atomically or flag running shared work for its worker."""

        timestamp = _timestamp_ms(None)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    _SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
                ).fetchone()
                if row is None:
                    raise ProvisioningJobNotFoundError(
                        "provisioning job not found", job_id
                    )
                job = _job_from_row(row)
                match job.status:
                    case ProvisioningJobStatus.QUEUED:
                        connection.execute(
                            """
                            UPDATE provision_job
                            SET status = 'CANCELLED', stage = 'CANCELLED',
                                cancellation_requested = 1, updated_at_ms = ?
                            WHERE job_id = ? AND status = 'QUEUED'
                            """,
                            (timestamp, job_id),
                        )
                    case ProvisioningJobStatus.RUNNING:
                        connection.execute(
                            """
                            UPDATE provision_job
                            SET cancellation_requested = 1, updated_at_ms = ?
                            WHERE job_id = ? AND status = 'RUNNING'
                            """,
                            (timestamp, job_id),
                        )
                    case (
                        ProvisioningJobStatus.SUCCEEDED
                        | ProvisioningJobStatus.FAILED
                        | ProvisioningJobStatus.CANCELLED
                    ):
                        raise ProvisioningJobTransitionError(
                            "provisioning job is already terminal", job_id, job.status
                        )
                updated = connection.execute(
                    _SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
                ).fetchone()
                if updated is None:
                    raise ProvisioningQueueStorageError(
                        "provisioning queue lost a cancelled job"
                    )
                connection.commit()
                return _job_from_row(updated)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue could not cancel a job"
            ) from error

    def requeue_expired(
        self, *, now: datetime | None = None
    ) -> tuple[ProvisioningJob, ...]:
        """Recover expired leases until their bounded retry budget is exhausted."""

        timestamp = _timestamp_ms(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._requeue_expired(connection, timestamp)
                rows = connection.execute(
                    _SELECT_JOB_SQL
                    + " WHERE status IN ('QUEUED', 'FAILED', 'CANCELLED') ORDER BY updated_at_ms, rowid"
                ).fetchall()
                connection.commit()
                return tuple(_job_from_row(row) for row in rows)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue could not recover expired jobs"
            ) from error

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self._path,
            timeout=self._busy_timeout_ms / 1_000,
            isolation_level=None,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
            connection.execute("PRAGMA synchronous = NORMAL")
            yield connection
        finally:
            connection.close()

    def _runtime_settings(self, connection: sqlite3.Connection) -> QueueRuntimeSettings:
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        foreign_keys_enabled = bool(
            connection.execute("PRAGMA foreign_keys").fetchone()[0]
        )
        busy_timeout_ms = int(connection.execute("PRAGMA busy_timeout").fetchone()[0])
        synchronous_value = int(connection.execute("PRAGMA synchronous").fetchone()[0])
        synchronous = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}.get(
            synchronous_value, "UNKNOWN"
        )
        return QueueRuntimeSettings(
            journal_mode=journal_mode.upper(),
            foreign_keys_enabled=foreign_keys_enabled,
            busy_timeout_ms=busy_timeout_ms,
            synchronous=synchronous,
        )

    def _requeue_expired(self, connection: sqlite3.Connection, timestamp: int) -> None:
        rows = connection.execute(
            _SELECT_JOB_SQL + " WHERE status = 'RUNNING' AND lease_expires_at_ms <= ?",
            (timestamp,),
        ).fetchall()
        for row in rows:
            job = _job_from_row(row)
            if job.cancellation_requested:
                connection.execute(_RECOVER_CANCELLED_SQL, (timestamp, job.job_id))
            elif job.attempts >= self._max_attempts:
                connection.execute(_RECOVER_FAILED_SQL, (timestamp, job.job_id))
            else:
                connection.execute(_RECOVER_QUEUED_SQL, (timestamp, job.job_id))

    def _update_live_lease(
        self, job_id: ProvisioningJobId, worker_id: str, *, timestamp: int, expiry: int
    ) -> ProvisioningJob:
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                updated = connection.execute(
                    """
                    UPDATE provision_job
                    SET lease_expires_at_ms = ?, lease_heartbeat_at_ms = ?, updated_at_ms = ?
                    WHERE job_id = ? AND status = 'RUNNING' AND lease_owner = ?
                      AND lease_expires_at_ms > ?
                    RETURNING job_id
                    """,
                    (expiry, timestamp, timestamp, job_id, worker_id, timestamp),
                ).fetchone()
                if updated is None:
                    self._raise_lease_error(connection, job_id)
                row = connection.execute(
                    _SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
                ).fetchone()
                if row is None:
                    raise ProvisioningQueueStorageError(
                        "provisioning queue lost a heartbeated job"
                    )
                connection.commit()
                return _job_from_row(row)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue could not heartbeat a job"
            ) from error

    def _terminalize(
        self,
        job_id: ProvisioningJobId,
        worker_id: str,
        *,
        status: ProvisioningJobStatus,
        detail: str,
    ) -> ProvisioningJob:
        worker = _required_metadata(worker_id, field_name="worker_id")
        timestamp = _timestamp_ms(None)
        match status:
            case ProvisioningJobStatus.SUCCEEDED:
                result, error = detail, None
            case ProvisioningJobStatus.FAILED:
                result, error = None, detail
            case (
                ProvisioningJobStatus.QUEUED
                | ProvisioningJobStatus.RUNNING
                | ProvisioningJobStatus.CANCELLED
            ):
                raise ProvisioningQueueValidationError(
                    "only successful or failed terminal queue statuses are supported"
                )
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                updated = connection.execute(
                    """
                    UPDATE provision_job
                    SET status = ?, stage = ?, result = ?, error = ?, lease_owner = NULL,
                        lease_expires_at_ms = NULL, lease_heartbeat_at_ms = NULL,
                        updated_at_ms = ?
                    WHERE job_id = ? AND status = 'RUNNING' AND lease_owner = ?
                      AND lease_expires_at_ms > ?
                    RETURNING job_id
                    """,
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
                    self._raise_lease_error(connection, job_id)
                row = connection.execute(
                    _SELECT_JOB_SQL + " WHERE job_id = ?", (job_id,)
                ).fetchone()
                if row is None:
                    raise ProvisioningQueueStorageError(
                        "provisioning queue lost a terminal job"
                    )
                connection.commit()
                return _job_from_row(row)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue could not terminalize a job"
            ) from error

    def _raise_lease_error(
        self, connection: sqlite3.Connection, job_id: ProvisioningJobId
    ) -> None:
        row = connection.execute(
            "SELECT status FROM provision_job WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise ProvisioningJobNotFoundError("provisioning job not found", job_id)
        raise ProvisioningJobLeaseError(
            "provisioning worker does not hold a live lease", job_id
        )


_CREATE_SCHEMA_SQL: Final = """
CREATE TABLE IF NOT EXISTS provision_job (
    job_id TEXT PRIMARY KEY,
    goal_identity TEXT NOT NULL,
    goal_type TEXT NOT NULL CHECK (goal_type IN (
        'ENSURE_CURRENT_SYMBOL', 'SYNC_DATASET_RANGE', 'FINALIZE_MARKET_SESSION'
    )),
    status TEXT NOT NULL CHECK (status IN (
        'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED'
    )),
    priority INTEGER NOT NULL CHECK (priority >= 0 AND priority <= 1000),
    stage TEXT NOT NULL,
    payload_version INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    lease_owner TEXT,
    lease_expires_at_ms INTEGER,
    lease_heartbeat_at_ms INTEGER,
    origin TEXT,
    correlation_id TEXT,
    cancellation_requested INTEGER NOT NULL DEFAULT 0 CHECK (
        cancellation_requested IN (0, 1)
    ),
    result TEXT,
    error TEXT,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS active_provision_job_identity
ON provision_job(goal_identity)
WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX IF NOT EXISTS queued_provision_job_order
ON provision_job(priority DESC, created_at_ms ASC, job_id ASC)
WHERE status = 'QUEUED';
"""

_SELECT_JOB_SQL: Final = """
SELECT job_id, goal_identity, status, priority, stage, attempts, lease_owner,
       lease_expires_at_ms, lease_heartbeat_at_ms, origin, correlation_id,
       cancellation_requested, result, error, created_at_ms, updated_at_ms, payload_json
FROM provision_job
"""

_INSERT_JOB_SQL: Final = """
INSERT INTO provision_job (
    job_id, goal_identity, goal_type, status, priority, stage, payload_version,
    payload_json, origin, correlation_id, created_at_ms, updated_at_ms
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_RECOVER_CANCELLED_SQL: Final = """
UPDATE provision_job
SET status = 'CANCELLED', stage = 'CANCELLED', lease_owner = NULL,
    lease_expires_at_ms = NULL, lease_heartbeat_at_ms = NULL, updated_at_ms = ?
WHERE job_id = ? AND status = 'RUNNING'
"""
_RECOVER_FAILED_SQL: Final = """
UPDATE provision_job
SET status = 'FAILED', stage = 'FAILED', error = 'lease retry limit exhausted',
    lease_owner = NULL, lease_expires_at_ms = NULL, lease_heartbeat_at_ms = NULL,
    updated_at_ms = ?
WHERE job_id = ? AND status = 'RUNNING'
"""
_RECOVER_QUEUED_SQL: Final = """
UPDATE provision_job
SET status = 'QUEUED', stage = 'QUEUED', lease_owner = NULL,
    lease_expires_at_ms = NULL, lease_heartbeat_at_ms = NULL, updated_at_ms = ?
WHERE job_id = ? AND status = 'RUNNING'
"""


def _validated_goal(goal: ProvisioningGoal) -> ProvisioningGoal:
    try:
        return parse_goal_payload(goal.payload_json())
    except (AttributeError, InvalidProvisioningGoalError):
        raise ProvisioningQueueValidationError("invalid provisioning goal") from None


def _job_from_row(row: sqlite3.Row) -> ProvisioningJob:
    try:
        return ProvisioningJob(
            job_id=ProvisioningJobId(str(row["job_id"])),
            goal_identity=str(row["goal_identity"]),
            goal=parse_goal_payload(str(row["payload_json"])),
            status=ProvisioningJobStatus(str(row["status"])),
            priority=int(row["priority"]),
            stage=str(row["stage"]),
            attempts=int(row["attempts"]),
            lease_owner=_optional_text(row["lease_owner"]),
            lease_expires_at=_optional_datetime(row["lease_expires_at_ms"]),
            lease_heartbeat_at=_optional_datetime(row["lease_heartbeat_at_ms"]),
            origin=_optional_text(row["origin"]),
            correlation_id=_optional_text(row["correlation_id"]),
            cancellation_requested=bool(row["cancellation_requested"]),
            result=_optional_text(row["result"]),
            error=_optional_text(row["error"]),
            created_at=_datetime_from_timestamp(int(row["created_at_ms"])),
            updated_at=_datetime_from_timestamp(int(row["updated_at_ms"])),
        )
    except (KeyError, TypeError, ValueError, InvalidProvisioningGoalError) as error:
        raise ProvisioningQueueStorageError(
            "provisioning queue contains invalid data"
        ) from error


def _timestamp_ms(now: datetime | None) -> int:
    resolved = datetime.now(UTC) if now is None else now.astimezone(UTC)
    return int(resolved.timestamp() * 1_000)


def _datetime_from_timestamp(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1_000, UTC)


def _optional_datetime(value: int | None) -> datetime | None:
    return None if value is None else _datetime_from_timestamp(value)


def _optional_text(value: str | None) -> str | None:
    return None if value is None else str(value)


def _validated_positive(value: int, *, field_name: str, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= maximum
    ):
        raise ProvisioningQueueValidationError(f"{field_name} must be bounded")
    return value


def _validated_priority(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= MAX_QUEUE_PRIORITY
    ):
        raise ProvisioningQueueValidationError("priority must be bounded")
    return value


def _validated_metadata(value: str | None, *, field_name: str) -> str | None:
    return None if value is None else _required_metadata(value, field_name=field_name)


def _required_metadata(value: str, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > MAX_QUEUE_METADATA_BYTES
        or any(character in value for character in "\r\n\x00")
    ):
        raise ProvisioningQueueValidationError(f"{field_name} must be bounded metadata")
    return value


def _validated_detail(value: str, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode("utf-8")) > MAX_QUEUE_DETAIL_BYTES
    ):
        raise ProvisioningQueueValidationError(f"{field_name} must be bounded")
    return value
