from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from time import sleep

import duckdb
import pytest
from typer.testing import CliRunner

import vnalpha.provisioning_queue.handlers as handlers_module
from vnalpha.cli import app
from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.provisioning_queue import (
    EnsureCurrentSymbolGoal,
    GoalEnrichment,
    ProvisioningJobStatus,
    ProvisioningQueue,
    QueueDataset,
    QueueEntityType,
    SyncDatasetRangeGoal,
)
from vnalpha.provisioning_queue.handlers import CurrentSymbolGoalHandler, HandlerResult
from vnalpha.provisioning_queue.models import GoalType, ProvisioningGoal
from vnalpha.provisioning_queue.worker import (
    ProvisioningWorker,
    ProvisioningWorkerConfigurationError,
    WorkerSettings,
)


def test_sequential_provisioning_worker_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_path = tmp_path / "provisioning.sqlite3"
    warehouse_path = tmp_path / "warehouse.duckdb"
    goal = _current_goal("FPT")
    queue = _CrashBeforeCompletionQueue(queue_path)
    queue.initialize()
    submitted = queue.submit_or_join(goal, priority=1).job
    effects: list[str] = []

    class ReplanningHandler:
        goal_type = GoalType.ENSURE_CURRENT_SYMBOL
        requires_warehouse_write = True

        def execute(
            self, _: ProvisioningGoal, connection: duckdb.DuckDBPyConnection | None
        ) -> HandlerResult:
            assert connection is not None
            connection.execute(
                "CREATE TABLE IF NOT EXISTS worker_effect(symbol VARCHAR PRIMARY KEY)"
            )
            persisted = connection.execute(
                "SELECT count(*) FROM worker_effect WHERE symbol = 'FPT'"
            ).fetchone()
            assert persisted is not None
            if persisted[0] == 0:
                connection.execute("INSERT INTO worker_effect VALUES ('FPT')")
                effects.append("CREATED")
                return HandlerResult(True, "CREATED")
            effects.append("REUSED")
            return HandlerResult(True, "REUSED")

    worker = ProvisioningWorker(
        queue,
        worker_id="worker-one",
        warehouse_path=warehouse_path,
        handlers=(ReplanningHandler(),),
    )
    with pytest.raises(KeyboardInterrupt):
        worker.process_one()
    assert queue.get(submitted.job_id).status is ProvisioningJobStatus.RUNNING
    queue.requeue_expired(now=datetime.now(UTC) + timedelta(seconds=61))

    restarted_queue = ProvisioningQueue(queue_path)
    restarted = ProvisioningWorker(
        restarted_queue,
        worker_id="worker-two",
        warehouse_path=warehouse_path,
        handlers=(ReplanningHandler(),),
    ).process_one()
    assert restarted is not None
    assert restarted.status is ProvisioningJobStatus.SUCCEEDED
    assert effects == ["CREATED", "REUSED"]

    unsupported = restarted_queue.submit_or_join(_range_goal("VNINDEX"), priority=1).job
    unsupported_worker = ProvisioningWorker(
        restarted_queue,
        worker_id="unsupported",
        warehouse_path=tmp_path / "never-opened.duckdb",
        handlers=(),
    )
    assert unsupported_worker.process_one().error == "UNSUPPORTED_GOAL_HANDLER"
    assert (
        restarted_queue.get(unsupported.job_id).status is ProvisioningJobStatus.FAILED
    )
    assert not (tmp_path / "never-opened.duckdb").exists()

    cancellation_race_unknown_queue = _CancelBeforeFailureQueue(
        tmp_path / "cancellation-race-unknown.sqlite3"
    )
    cancellation_race_unknown_queue.initialize()
    cancellation_race_unknown_queue.submit_or_join(_range_goal("VN30"), priority=1)
    unknown_cancellation_result = ProvisioningWorker(
        cancellation_race_unknown_queue,
        worker_id="cancellation-race-unknown",
        handlers=(),
    ).process_one()
    assert unknown_cancellation_result.status is ProvisioningJobStatus.CANCELLED

    unsupported_enrichment = restarted_queue.submit_or_join(
        _current_goal("VIC").model_copy(
            update={"requested_enrichments": (GoalEnrichment.FLOW_CONTEXT,)}
        ),
        priority=1,
    ).job
    monkeypatch.setattr(
        handlers_module,
        "ensure_current_symbol_ready",
        lambda *_args, **_kwargs: pytest.fail("unsupported enrichment called provider"),
    )
    enrichment_result = ProvisioningWorker(
        restarted_queue,
        worker_id="unsupported-enrichment",
        warehouse_path=tmp_path / "unsupported-enrichment.duckdb",
        handlers=(CurrentSymbolGoalHandler(),),
    ).process_one()
    assert enrichment_result.error == "UNSUPPORTED_ENRICHMENT_REQUEST"
    assert (
        restarted_queue.get(unsupported_enrichment.job_id).status
        is ProvisioningJobStatus.FAILED
    )

    cancelled = restarted_queue.submit_or_join(_current_goal("HPG"), priority=1).job

    class CancellingHandler:
        goal_type = GoalType.ENSURE_CURRENT_SYMBOL
        requires_warehouse_write = True

        def execute(
            self, _: ProvisioningGoal, connection: duckdb.DuckDBPyConnection | None
        ) -> HandlerResult:
            assert connection is not None
            connection.execute("CREATE TABLE cancellation_boundary(value INTEGER)")
            restarted_queue.cancel(cancelled.job_id)
            return HandlerResult(True, "should not complete")

    cancelled_result = ProvisioningWorker(
        restarted_queue,
        worker_id="cancelling",
        warehouse_path=warehouse_path,
        handlers=(CancellingHandler(),),
    ).process_one()
    assert cancelled_result.status is ProvisioningJobStatus.CANCELLED

    cancellation_race_queue = _CancelBeforeCompletionQueue(
        tmp_path / "cancellation-race.sqlite3"
    )
    cancellation_race_queue.initialize()
    cancellation_race_queue.submit_or_join(_current_goal("SSI"), priority=1)

    class SuccessfulHandler:
        goal_type = GoalType.ENSURE_CURRENT_SYMBOL
        requires_warehouse_write = False

        def execute(
            self, _: ProvisioningGoal, __: duckdb.DuckDBPyConnection | None
        ) -> HandlerResult:
            return HandlerResult(True, "success")

    cancellation_race = ProvisioningWorker(
        cancellation_race_queue,
        worker_id="cancellation-race",
        handlers=(SuccessfulHandler(),),
    ).process_one()
    assert cancellation_race.status is ProvisioningJobStatus.CANCELLED

    short_lease_queue = ProvisioningQueue(
        tmp_path / "short-lease.sqlite3", lease_seconds=2
    )
    with pytest.raises(ProvisioningWorkerConfigurationError):
        ProvisioningWorker(
            short_lease_queue,
            worker_id="invalid-lease",
            settings=WorkerSettings(stage_timeout_seconds=1, lease_safety_seconds=1),
        )

    overrun_queue = ProvisioningQueue(tmp_path / "overrun.sqlite3", lease_seconds=3)
    overrun_queue.initialize()
    overrun_queue.submit_or_join(_current_goal("VCB"), priority=1)
    stage_started = Event()
    release_stage = Event()

    class OverrunHandler:
        goal_type = GoalType.ENSURE_CURRENT_SYMBOL
        requires_warehouse_write = True

        def execute(
            self, _: ProvisioningGoal, connection: duckdb.DuckDBPyConnection | None
        ) -> HandlerResult:
            assert connection is not None
            connection.execute("CREATE TABLE overrun_effect(value INTEGER)")
            connection.execute("INSERT INTO overrun_effect VALUES (1)")
            stage_started.set()
            assert release_stage.wait(timeout=5)
            return HandlerResult(True, "late success")

    overrun_worker = ProvisioningWorker(
        overrun_queue,
        worker_id="overrun",
        warehouse_path=tmp_path / "overrun.duckdb",
        handlers=(OverrunHandler(),),
        settings=WorkerSettings(stage_timeout_seconds=1, lease_safety_seconds=1),
    )
    overrun_result: list[object] = []
    worker_thread = Thread(
        target=lambda: overrun_result.append(overrun_worker.process_one())
    )
    worker_thread.start()
    assert stage_started.wait(timeout=2)
    sleep(3.2)
    assert not overrun_queue.requeue_expired()
    release_stage.set()
    worker_thread.join(timeout=5)
    assert not worker_thread.is_alive()
    assert overrun_result[0].status is ProvisioningJobStatus.FAILED
    assert overrun_result[0].error == "STAGE_TIMEOUT"

    exclusive_queue = ProvisioningQueue(tmp_path / "exclusive.sqlite3")
    exclusive_queue.initialize()
    first_exclusive = exclusive_queue.submit_or_join(
        _current_goal("ACB"), priority=2
    ).job
    second_exclusive = exclusive_queue.submit_or_join(
        _current_goal("VIC"), priority=1
    ).job
    first_stage_started = Event()
    release_first_stage = Event()

    class ExclusiveHandler:
        goal_type = GoalType.ENSURE_CURRENT_SYMBOL
        requires_warehouse_write = True

        def execute(
            self, goal: ProvisioningGoal, connection: duckdb.DuckDBPyConnection | None
        ) -> HandlerResult:
            assert connection is not None
            if goal.symbol == "ACB":
                first_stage_started.set()
                assert release_first_stage.wait(timeout=5)
            return HandlerResult(True, goal.symbol)

    first_worker = ProvisioningWorker(
        exclusive_queue,
        worker_id="exclusive-one",
        warehouse_path=tmp_path / "exclusive.duckdb",
        handlers=(ExclusiveHandler(),),
    )
    exclusive_alias_path = tmp_path / "exclusive-alias.sqlite3"
    exclusive_alias_path.hardlink_to(exclusive_queue.path)
    second_worker = ProvisioningWorker(
        ProvisioningQueue(exclusive_alias_path),
        worker_id="exclusive-two",
        warehouse_path=tmp_path / "exclusive.duckdb",
        handlers=(ExclusiveHandler(),),
    )
    first_thread = Thread(target=first_worker.process_one)
    second_thread = Thread(target=second_worker.process_one)
    first_thread.start()
    assert first_stage_started.wait(timeout=2)
    second_thread.start()
    sleep(0.1)
    assert (
        exclusive_queue.get(first_exclusive.job_id).status
        is ProvisioningJobStatus.RUNNING
    )
    assert (
        exclusive_queue.get(second_exclusive.job_id).status
        is ProvisioningJobStatus.QUEUED
    )
    release_first_stage.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)
    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert (
        exclusive_queue.get(second_exclusive.job_id).status
        is ProvisioningJobStatus.SUCCEEDED
    )

    cli_queue_path = tmp_path / "cli.sqlite3"
    cli_queue = ProvisioningQueue(cli_queue_path)
    cli_queue.initialize()
    first_cli_job = cli_queue.submit_or_join(_range_goal("VN30"), priority=2).job
    second_cli_job = cli_queue.submit_or_join(_range_goal("HNX30"), priority=1).job
    cli_result = CliRunner().invoke(
        app,
        [
            "provision",
            "worker",
            "--once",
            "--queue-path",
            str(cli_queue_path),
            "--warehouse-path",
            str(tmp_path / "cli-warehouse.duckdb"),
            "--worker-id",
            "cli-worker",
        ],
        catch_exceptions=False,
    )
    assert cli_result.exit_code == 0
    assert "processed=1" in cli_result.output
    assert cli_queue.get(first_cli_job.job_id).status is ProvisioningJobStatus.FAILED
    assert cli_queue.get(second_cli_job.job_id).status is ProvisioningJobStatus.QUEUED


class _CrashBeforeCompletionQueue(ProvisioningQueue):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._crash_once = True

    def complete(self, job_id, worker_id: str, result: str):
        if self._crash_once:
            self._crash_once = False
            raise KeyboardInterrupt
        return super().complete(job_id, worker_id, result)


class _CancelBeforeCompletionQueue(ProvisioningQueue):
    def complete(self, job_id, worker_id: str, result: str):
        self.cancel(job_id)
        return super().complete(job_id, worker_id, result)


class _CancelBeforeFailureQueue(ProvisioningQueue):
    def fail(self, job_id, worker_id: str, error: str):
        self.cancel(job_id)
        return super().fail(job_id, worker_id, error)


def _current_goal(symbol: str) -> EnsureCurrentSymbolGoal:
    return EnsureCurrentSymbolGoal(
        symbol=symbol,
        effective_date=date(2026, 7, 21),
        desired_capability=ReadinessCapability.PRICE_ANALYSIS,
        source_policy_version="policy-v1",
        contract_version="current-symbol-v1",
    )


def _range_goal(entity_id: str) -> SyncDatasetRangeGoal:
    return SyncDatasetRangeGoal(
        dataset=QueueDataset.INDEX_OHLCV,
        entity_type=QueueEntityType.INDEX,
        entity_id=entity_id,
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 21),
        source_policy_version="policy-v1",
        contract_version="dataset-range-v1",
    )
