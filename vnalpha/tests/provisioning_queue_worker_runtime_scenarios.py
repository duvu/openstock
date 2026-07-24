from __future__ import annotations

from pathlib import Path
from threading import Event, Thread
from time import sleep

import duckdb
from typer.testing import CliRunner

from tests.provisioning_queue_worker_support import (
    StagedHandler,
    current_goal,
    range_goal,
    stage,
)
from vnalpha.cli import app
from vnalpha.provisioning_queue import ProvisioningJobStatus, ProvisioningQueue
from vnalpha.provisioning_queue.handlers import HandlerResult
from vnalpha.provisioning_queue.worker import ProvisioningWorker


def assert_worker_runtime_boundaries(tmp_path: Path) -> None:
    _assert_workers_share_one_queue_inode_lock(tmp_path)
    _assert_cli_worker_claims_one_job(tmp_path)


def _assert_workers_share_one_queue_inode_lock(tmp_path: Path) -> None:
    queue = ProvisioningQueue(tmp_path / "exclusive.sqlite3")
    queue.initialize()
    first = queue.submit_or_join(current_goal("ACB"), priority=2).job
    second = queue.submit_or_join(current_goal("VIC"), priority=1).job
    first_stage_started = Event()
    release_first_stage = Event()

    def exclusive(
        connection: duckdb.DuckDBPyConnection | None,
    ) -> HandlerResult:
        assert connection is not None
        if not first_stage_started.is_set():
            first_stage_started.set()
            assert release_first_stage.wait(timeout=5)
        return HandlerResult(True, "DONE")

    handler = StagedHandler((stage("exclusive", True, exclusive),))
    first_worker = ProvisioningWorker(
        queue,
        worker_id="exclusive-one",
        warehouse_path=tmp_path / "exclusive.duckdb",
        handlers=(handler,),
    )
    alias_path = tmp_path / "exclusive-alias.sqlite3"
    alias_path.hardlink_to(queue.path)
    second_worker = ProvisioningWorker(
        ProvisioningQueue(alias_path),
        worker_id="exclusive-two",
        warehouse_path=tmp_path / "exclusive.duckdb",
        handlers=(handler,),
    )
    first_thread = Thread(target=first_worker.process_one)
    second_thread = Thread(target=second_worker.process_one)
    first_thread.start()
    assert first_stage_started.wait(timeout=2)
    second_thread.start()
    sleep(0.1)
    assert queue.get(first.job_id).status is ProvisioningJobStatus.RUNNING
    assert queue.get(second.job_id).status is ProvisioningJobStatus.QUEUED
    release_first_stage.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)
    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert queue.get(second.job_id).status is ProvisioningJobStatus.SUCCEEDED


def _assert_cli_worker_claims_one_job(tmp_path: Path) -> None:
    queue_path = tmp_path / "cli.sqlite3"
    queue = ProvisioningQueue(queue_path)
    queue.initialize()
    first = queue.submit_or_join(range_goal("VN30"), priority=2).job
    second = queue.submit_or_join(range_goal("HNX30"), priority=1).job
    result = CliRunner().invoke(
        app,
        [
            "provision",
            "worker",
            "--once",
            "--queue-path",
            str(queue_path),
            "--warehouse-path",
            str(tmp_path / "cli-warehouse.duckdb"),
            "--worker-id",
            "cli-worker",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "processed=1" in result.output
    assert queue.get(first.job_id).status is ProvisioningJobStatus.FAILED
    assert queue.get(second.job_id).status is ProvisioningJobStatus.QUEUED
