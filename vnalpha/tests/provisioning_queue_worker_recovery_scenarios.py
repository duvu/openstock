from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from tests.provisioning_queue_worker_support import (
    CrashBeforeCompletionQueue,
    StagedHandler,
    current_goal,
    stage,
)
from vnalpha.provisioning_queue import ProvisioningJobStatus, ProvisioningQueue
from vnalpha.provisioning_queue.handlers import HandlerResult
from vnalpha.provisioning_queue.worker import ProvisioningWorker


def assert_worker_recovery_boundaries(tmp_path: Path) -> None:
    _assert_retry_reuses_committed_effect(tmp_path)
    _assert_hard_interruption_rolls_back_active_stage(tmp_path)


def _assert_retry_reuses_committed_effect(tmp_path: Path) -> None:
    queue_path = tmp_path / "recovery.sqlite3"
    warehouse_path = tmp_path / "recovery.duckdb"
    queue = CrashBeforeCompletionQueue(queue_path)
    queue.initialize()
    submitted = queue.submit_or_join(current_goal("FPT"), priority=1).job
    effects: list[str] = []

    def replan(connection: duckdb.DuckDBPyConnection | None) -> HandlerResult:
        assert connection is not None
        connection.execute(
            "CREATE TABLE IF NOT EXISTS worker_effect(symbol VARCHAR PRIMARY KEY)"
        )
        row = connection.execute(
            "SELECT count(*) FROM worker_effect WHERE symbol = 'FPT'"
        ).fetchone()
        assert row is not None
        if row[0] == 0:
            connection.execute("INSERT INTO worker_effect VALUES ('FPT')")
            effects.append("CREATED")
            return HandlerResult(True, "CREATED")
        effects.append("REUSED")
        return HandlerResult(True, "REUSED")

    worker = ProvisioningWorker(
        queue,
        worker_id="recovery-one",
        warehouse_path=warehouse_path,
        handlers=(StagedHandler((stage("replan", True, replan),)),),
    )
    with pytest.raises(KeyboardInterrupt):
        worker.process_one()
    assert queue.get(submitted.job_id).status is ProvisioningJobStatus.RUNNING
    queue.requeue_expired(now=datetime.now(UTC) + timedelta(seconds=61))
    restarted = ProvisioningWorker(
        ProvisioningQueue(queue_path),
        worker_id="recovery-two",
        warehouse_path=warehouse_path,
        handlers=(StagedHandler((stage("replan", True, replan),)),),
    ).process_one()
    assert restarted is not None
    assert restarted.status is ProvisioningJobStatus.SUCCEEDED
    assert effects == ["CREATED", "REUSED"]


def _assert_hard_interruption_rolls_back_active_stage(tmp_path: Path) -> None:
    queue = ProvisioningQueue(tmp_path / "interrupt.sqlite3")
    queue.initialize()
    submitted = queue.submit_or_join(current_goal("HPG"), priority=1).job
    warehouse_path = tmp_path / "interrupt.duckdb"
    interrupted = True

    def write_or_interrupt(
        connection: duckdb.DuckDBPyConnection | None,
    ) -> HandlerResult:
        nonlocal interrupted
        assert connection is not None
        connection.execute("CREATE TABLE interrupted_effect(value INTEGER)")
        connection.execute("INSERT INTO interrupted_effect VALUES (1)")
        if interrupted:
            interrupted = False
            raise KeyboardInterrupt
        return HandlerResult(True, "RECOVERED")

    worker = ProvisioningWorker(
        queue,
        worker_id="interrupt-worker",
        warehouse_path=warehouse_path,
        handlers=(StagedHandler((stage("interruptible", True, write_or_interrupt),)),),
    )
    with pytest.raises(KeyboardInterrupt):
        worker.process_one()
    assert queue.get(submitted.job_id).status is ProvisioningJobStatus.RUNNING
    assert _table_count(warehouse_path, "interrupted_effect") == 0
    queue.requeue_expired(now=datetime.now(UTC) + timedelta(seconds=61))
    recovered = worker.process_one()
    assert recovered is not None
    assert recovered.status is ProvisioningJobStatus.SUCCEEDED
    assert _table_count(warehouse_path, "interrupted_effect") == 1


def _table_count(path: Path, table_name: str) -> int:
    with duckdb.connect(str(path), read_only=True) as connection:
        row = connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()
    assert row is not None
    return row[0]
