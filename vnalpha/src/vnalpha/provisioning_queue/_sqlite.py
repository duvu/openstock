from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from os import R_OK, W_OK, access, environ
from pathlib import Path
from shutil import disk_usage
from typing import Final, Iterator

from vnalpha.provisioning_queue.queue_models import (
    ProvisioningQueueStorageError,
    QueueCheckpointResult,
    QueueHealthReport,
    QueueRuntimeSettings,
)

_QUEUE_PATH_ENV_VAR: Final = "VNALPHA_PROVISIONING_QUEUE_PATH"
_SYSTEM_QUEUE_PATH: Final = Path("/var/lib/openstock/queue/provisioning.sqlite3")
_configured_queue_path = environ.get(_QUEUE_PATH_ENV_VAR, "").strip()
DEFAULT_QUEUE_PATH: Final = (
    Path(_configured_queue_path).expanduser()
    if _configured_queue_path
    else _SYSTEM_QUEUE_PATH
)
DEFAULT_BUSY_TIMEOUT_MS: Final = 1_000
DEFAULT_LEASE_SECONDS: Final = 60
DEFAULT_MAX_ATTEMPTS: Final = 3
MIN_FREE_DISK_BYTES: Final = 100 * 1024 * 1024
SCHEMA_VERSION: Final = 3


@dataclass(frozen=True, slots=True)
class QueueConfiguration:
    path: Path
    busy_timeout_ms: int
    lease_seconds: int
    max_attempts: int


class QueueDatabase:
    def __init__(self, configuration: QueueConfiguration) -> None:
        self.configuration = configuration

    def initialize(self) -> QueueRuntimeSettings:
        try:
            self.configuration.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connection() as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version == 0:
                    connection.executescript(CREATE_SCHEMA_SQL)
                    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    self._record_migration(connection)
                elif version == 1:
                    self._migrate_v1_to_v2(connection)
                    self._migrate_v2_to_v3(connection)
                elif version == 2:
                    self._migrate_v2_to_v3(connection)
                elif version != SCHEMA_VERSION:
                    raise ProvisioningQueueStorageError(
                        "unsupported provisioning queue schema version"
                    )
                return self.runtime_settings_from(connection)
        except (OSError, sqlite3.Error) as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue storage is unavailable"
            ) from error

    def health(self, now: datetime | None = None) -> QueueHealthReport:
        """Inspect an existing queue without creating or repairing it."""

        inspected_at = datetime.now(UTC) if now is None else now.astimezone(UTC)
        file_size_bytes, wal_size_bytes, readable, writable, disk_free_bytes = (
            self._filesystem_state()
        )
        if not self.configuration.path.exists():
            return QueueHealthReport(
                schema_version=None,
                supported_schema=False,
                integrity_check="NOT_RUN",
                integrity_ok=False,
                journal_mode=None,
                synchronous=None,
                busy_timeout_ms=None,
                file_size_bytes=file_size_bytes,
                wal_size_bytes=wal_size_bytes,
                disk_free_bytes=disk_free_bytes,
                disk_free_threshold_bytes=MIN_FREE_DISK_BYTES,
                disk_free_above_threshold=_has_disk_space(disk_free_bytes),
                readable=readable,
                writable=writable,
                active_leases=None,
                expired_leases=None,
                queue_depth=None,
                oldest_queued_age_seconds=None,
                last_checkpoint_at=None,
                last_prune_at=None,
                last_migration_at=None,
                detail="queue database file does not exist",
            )
        try:
            with self.readonly_connection() as connection:
                schema_version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                integrity_check = str(
                    connection.execute("PRAGMA integrity_check").fetchone()[0]
                )
                supported_schema = schema_version == SCHEMA_VERSION
                active_leases, expired_leases, queue_depth, oldest_age = (
                    self._queue_counts(connection, inspected_at)
                    if supported_schema
                    else (None, None, None, None)
                )
                checkpoint_at, prune_at, migration_at = (
                    self._maintenance_timestamps(connection)
                    if supported_schema
                    else (None, None, None)
                )
                return QueueHealthReport(
                    schema_version=schema_version,
                    supported_schema=supported_schema,
                    integrity_check=integrity_check,
                    integrity_ok=integrity_check.lower() == "ok",
                    journal_mode=str(
                        connection.execute("PRAGMA journal_mode").fetchone()[0]
                    ).upper(),
                    synchronous="NORMAL",
                    busy_timeout_ms=self.configuration.busy_timeout_ms,
                    file_size_bytes=file_size_bytes,
                    wal_size_bytes=wal_size_bytes,
                    disk_free_bytes=disk_free_bytes,
                    disk_free_threshold_bytes=MIN_FREE_DISK_BYTES,
                    disk_free_above_threshold=_has_disk_space(disk_free_bytes),
                    readable=readable,
                    writable=writable,
                    active_leases=active_leases,
                    expired_leases=expired_leases,
                    queue_depth=queue_depth,
                    oldest_queued_age_seconds=oldest_age,
                    last_checkpoint_at=checkpoint_at,
                    last_prune_at=prune_at,
                    last_migration_at=migration_at,
                    detail=None
                    if supported_schema
                    else "unsupported queue schema version",
                )
        except (OSError, sqlite3.Error) as error:
            return QueueHealthReport(
                schema_version=None,
                supported_schema=False,
                integrity_check="UNAVAILABLE",
                integrity_ok=False,
                journal_mode=None,
                synchronous=None,
                busy_timeout_ms=None,
                file_size_bytes=file_size_bytes,
                wal_size_bytes=wal_size_bytes,
                disk_free_bytes=disk_free_bytes,
                disk_free_threshold_bytes=MIN_FREE_DISK_BYTES,
                disk_free_above_threshold=_has_disk_space(disk_free_bytes),
                readable=readable,
                writable=writable,
                active_leases=None,
                expired_leases=None,
                queue_depth=None,
                oldest_queued_age_seconds=None,
                last_checkpoint_at=None,
                last_prune_at=None,
                last_migration_at=None,
                detail=f"queue health inspection failed: {error}",
            )

    def runtime_settings(self) -> QueueRuntimeSettings:
        try:
            with self.connection() as connection:
                return self.runtime_settings_from(connection)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue storage is unavailable"
            ) from error

    def checkpoint(self, now: datetime | None = None) -> QueueCheckpointResult:
        """Request a passive checkpoint that remains compatible with readers."""

        completed_at = datetime.now(UTC) if now is None else now.astimezone(UTC)
        try:
            with self.connection() as connection:
                self._set_metadata(
                    connection,
                    "last_checkpoint_at_ms",
                    int(completed_at.timestamp() * 1_000),
                )
                row = connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
                if row is None:
                    raise ProvisioningQueueStorageError(
                        "provisioning queue checkpoint returned no result"
                    )
                return QueueCheckpointResult(
                    busy_readers=int(row[0]),
                    wal_frames=int(row[1]),
                    checkpointed_frames=int(row[2]),
                    completed_at=completed_at,
                )
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue checkpoint failed"
            ) from error

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.configuration.path,
            timeout=self.configuration.busy_timeout_ms / 1_000,
            isolation_level=None,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                f"PRAGMA busy_timeout = {self.configuration.busy_timeout_ms}"
            )
            connection.execute("PRAGMA synchronous = NORMAL")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def readonly_connection(self) -> Iterator[sqlite3.Connection]:
        uri = f"{self.configuration.path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=self.configuration.busy_timeout_ms / 1_000,
            isolation_level=None,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute(
                f"PRAGMA busy_timeout = {self.configuration.busy_timeout_ms}"
            )
            yield connection
        finally:
            connection.close()

    def runtime_settings_from(
        self, connection: sqlite3.Connection
    ) -> QueueRuntimeSettings:
        synchronous_value = int(connection.execute("PRAGMA synchronous").fetchone()[0])
        return QueueRuntimeSettings(
            journal_mode=str(
                connection.execute("PRAGMA journal_mode").fetchone()[0]
            ).upper(),
            foreign_keys_enabled=bool(
                connection.execute("PRAGMA foreign_keys").fetchone()[0]
            ),
            busy_timeout_ms=int(
                connection.execute("PRAGMA busy_timeout").fetchone()[0]
            ),
            synchronous={0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}.get(
                synchronous_value, "UNKNOWN"
            ),
            lease_seconds=self.configuration.lease_seconds,
        )

    def _migrate_v1_to_v2(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(CREATE_QUEUE_METADATA_SQL)
            connection.execute(CREATE_PRUNED_PROVISION_JOB_SQL)
            connection.execute("PRAGMA user_version = 2")
            self._record_migration(connection)
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise

    def _migrate_v2_to_v3(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "ALTER TABLE provision_job ADD COLUMN available_at_ms INTEGER"
            )
            connection.execute(
                "UPDATE provision_job SET available_at_ms = created_at_ms "
                "WHERE available_at_ms IS NULL"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS queued_provision_job_available_order "
                "ON provision_job(available_at_ms, priority DESC, created_at_ms ASC, job_id ASC) "
                "WHERE status = 'QUEUED'"
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._record_migration(connection)
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise

    def _record_migration(self, connection: sqlite3.Connection) -> None:
        self._set_metadata(
            connection,
            "last_migration_at_ms",
            int(datetime.now(UTC).timestamp() * 1_000),
        )

    def _set_metadata(
        self, connection: sqlite3.Connection, key: str, value: int
    ) -> None:
        connection.execute(
            "INSERT INTO provisioning_queue_metadata (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

    def _filesystem_state(self) -> tuple[int, int, bool, bool, int | None]:
        path = self.configuration.path
        try:
            file_size_bytes = path.stat().st_size if path.exists() else 0
            wal_path = path.with_name(f"{path.name}-wal")
            wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0
            disk_free_bytes = disk_usage(path.parent).free
            return (
                file_size_bytes,
                wal_size_bytes,
                path.is_file() and access(path, R_OK),
                path.parent.is_dir() and access(path.parent, W_OK),
                disk_free_bytes,
            )
        except OSError:
            return 0, 0, False, False, None

    def _queue_counts(
        self, connection: sqlite3.Connection, inspected_at: datetime
    ) -> tuple[int, int, int, int | None]:
        timestamp = int(inspected_at.timestamp() * 1_000)
        row = connection.execute(
            "SELECT "
            "COUNT(*) FILTER (WHERE status = 'RUNNING' AND lease_expires_at_ms > ?), "
            "COUNT(*) FILTER (WHERE status = 'RUNNING' AND lease_expires_at_ms <= ?), "
            "COUNT(*) FILTER (WHERE status = 'QUEUED'), "
            "MIN(created_at_ms) FILTER (WHERE status = 'QUEUED') "
            "FROM provision_job",
            (timestamp, timestamp),
        ).fetchone()
        if row is None:
            raise ProvisioningQueueStorageError("queue health counts are unavailable")
        oldest = None if row[3] is None else max(0, (timestamp - int(row[3])) // 1_000)
        return int(row[0]), int(row[1]), int(row[2]), oldest

    def _maintenance_timestamps(
        self, connection: sqlite3.Connection
    ) -> tuple[datetime | None, datetime | None, datetime | None]:
        rows = connection.execute(
            "SELECT key, value FROM provisioning_queue_metadata "
            "WHERE key IN ('last_checkpoint_at_ms', 'last_prune_at_ms', 'last_migration_at_ms')"
        ).fetchall()
        values = {str(row[0]): int(row[1]) for row in rows}
        return (
            _datetime_from_metadata(values.get("last_checkpoint_at_ms")),
            _datetime_from_metadata(values.get("last_prune_at_ms")),
            _datetime_from_metadata(values.get("last_migration_at_ms")),
        )


CREATE_SCHEMA_SQL: Final = """
CREATE TABLE IF NOT EXISTS provision_job (
    job_id TEXT PRIMARY KEY, goal_identity TEXT NOT NULL,
    goal_type TEXT NOT NULL CHECK (goal_type IN ('ENSURE_CURRENT_SYMBOL', 'SYNC_DATASET_RANGE', 'FINALIZE_MARKET_SESSION')),
    status TEXT NOT NULL CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')),
    priority INTEGER NOT NULL CHECK (priority >= 0 AND priority <= 1000), stage TEXT NOT NULL,
    payload_version INTEGER NOT NULL, payload_json TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0), lease_owner TEXT,
    lease_expires_at_ms INTEGER, lease_heartbeat_at_ms INTEGER, origin TEXT, correlation_id TEXT,
    cancellation_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancellation_requested IN (0, 1)),
    result TEXT, error TEXT, available_at_ms INTEGER NOT NULL,
    created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS active_provision_job_identity
ON provision_job(goal_identity) WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX IF NOT EXISTS queued_provision_job_order
ON provision_job(priority DESC, created_at_ms ASC, job_id ASC) WHERE status = 'QUEUED';
CREATE INDEX IF NOT EXISTS queued_provision_job_available_order
ON provision_job(available_at_ms, priority DESC, created_at_ms ASC, job_id ASC)
WHERE status = 'QUEUED';
CREATE TABLE IF NOT EXISTS provisioning_queue_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pruned_provision_job (
    job_id TEXT PRIMARY KEY,
    final_status TEXT NOT NULL CHECK (final_status IN ('SUCCEEDED', 'FAILED', 'CANCELLED')),
    pruned_at_ms INTEGER NOT NULL
);
"""

CREATE_QUEUE_METADATA_SQL: Final = """
CREATE TABLE IF NOT EXISTS provisioning_queue_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

CREATE_PRUNED_PROVISION_JOB_SQL: Final = """
CREATE TABLE IF NOT EXISTS pruned_provision_job (
    job_id TEXT PRIMARY KEY,
    final_status TEXT NOT NULL CHECK (final_status IN ('SUCCEEDED', 'FAILED', 'CANCELLED')),
    pruned_at_ms INTEGER NOT NULL
)
"""

SELECT_JOB_SQL: Final = """
SELECT job_id, goal_identity, status, priority, stage, attempts, lease_owner,
       lease_expires_at_ms, lease_heartbeat_at_ms, origin, correlation_id,
       cancellation_requested, result, error, created_at_ms, updated_at_ms, payload_json
FROM provision_job
"""


def _has_disk_space(disk_free_bytes: int | None) -> bool:
    return disk_free_bytes is not None and disk_free_bytes >= MIN_FREE_DISK_BYTES


def _datetime_from_metadata(value: int | None) -> datetime | None:
    return None if value is None else datetime.fromtimestamp(value / 1_000, UTC)
