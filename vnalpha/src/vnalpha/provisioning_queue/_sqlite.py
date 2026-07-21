from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterator

from vnalpha.provisioning_queue.queue_models import (
    ProvisioningQueueStorageError,
    QueueRuntimeSettings,
)

DEFAULT_QUEUE_PATH: Final = Path("/var/lib/openstock/queue/provisioning.sqlite3")
DEFAULT_BUSY_TIMEOUT_MS: Final = 1_000
DEFAULT_LEASE_SECONDS: Final = 60
DEFAULT_MAX_ATTEMPTS: Final = 3
SCHEMA_VERSION: Final = 1


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
                elif version != SCHEMA_VERSION:
                    raise ProvisioningQueueStorageError(
                        "unsupported provisioning queue schema version"
                    )
                return self.runtime_settings_from(connection)
        except (OSError, sqlite3.Error) as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue storage is unavailable"
            ) from error

    def runtime_settings(self) -> QueueRuntimeSettings:
        try:
            with self.connection() as connection:
                return self.runtime_settings_from(connection)
        except sqlite3.Error as error:
            raise ProvisioningQueueStorageError(
                "provisioning queue storage is unavailable"
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
    result TEXT, error TEXT, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS active_provision_job_identity
ON provision_job(goal_identity) WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX IF NOT EXISTS queued_provision_job_order
ON provision_job(priority DESC, created_at_ms ASC, job_id ASC) WHERE status = 'QUEUED';
"""

SELECT_JOB_SQL: Final = """
SELECT job_id, goal_identity, status, priority, stage, attempts, lease_owner,
       lease_expires_at_ms, lease_heartbeat_at_ms, origin, correlation_id,
       cancellation_requested, result, error, created_at_ms, updated_at_ms, payload_json
FROM provision_job
"""
