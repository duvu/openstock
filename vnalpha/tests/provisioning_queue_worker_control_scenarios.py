from __future__ import annotations

import json
import signal
from pathlib import Path
from threading import Event, Thread
from time import sleep

import duckdb
import pytest

import vnalpha.provisioning_queue.handlers as handlers_module
from tests.provisioning_queue_worker_support import (
    CancelBeforeCompletionQueue,
    CancelBeforeFailureQueue,
    StagedHandler,
    current_goal,
    range_goal,
    stage,
)
from vnalpha.data_provisioning.ensure_current_symbol import (
    CurrentSymbolReadyResult,
    ProvisioningAction,
    ProvisioningOutcome,
)
from vnalpha.provisioning_queue import (
    GoalEnrichment,
    ProvisioningJobStatus,
    ProvisioningQueue,
)
from vnalpha.provisioning_queue.handlers import CurrentSymbolGoalHandler, HandlerResult
from vnalpha.provisioning_queue.worker import (
    ProvisioningWorker,
    ProvisioningWorkerConfigurationError,
    WorkerSettings,
)


def assert_stage_control_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_unsupported_handlers_fail_without_warehouse(tmp_path)
    _assert_enrichment_stops_before_provider(tmp_path, monkeypatch)
    _assert_current_symbol_result_retains_tail_evidence(tmp_path, monkeypatch)
    _assert_cancellation_stops_before_next_stage(tmp_path)
    _assert_terminalization_cancellation_races(tmp_path)
    _assert_timing_configuration_is_bounded(tmp_path)
    _assert_timeout_finishes_the_safe_boundary(tmp_path)
    _assert_signal_stop_leaves_current_job_recoverable(tmp_path)


def _assert_unsupported_handlers_fail_without_warehouse(tmp_path: Path) -> None:
    queue = ProvisioningQueue(tmp_path / "unsupported.sqlite3")
    queue.initialize()
    submitted = queue.submit_or_join(range_goal("VNINDEX"), priority=1).job
    warehouse_path = tmp_path / "never-opened.duckdb"
    result = ProvisioningWorker(
        queue,
        worker_id="unsupported",
        warehouse_path=warehouse_path,
        handlers=(),
    ).process_one()
    assert result is not None
    assert result.error == "UNSUPPORTED_GOAL_HANDLER"
    assert queue.get(submitted.job_id).status is ProvisioningJobStatus.FAILED


def _assert_enrichment_stops_before_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    company_context_stages = CurrentSymbolGoalHandler().stages(
        current_goal("FPT").model_copy(
            update={"requested_enrichments": (GoalEnrichment.COMPANY_CONTEXT,)}
        )
    )
    assert [stage.name for stage in company_context_stages] == [
        "current-symbol-admission",
        "current-symbol-provision",
        "company-context",
    ]
    queue = ProvisioningQueue(tmp_path / "enrichment.sqlite3")
    queue.initialize()
    submitted = queue.submit_or_join(
        current_goal("VIC").model_copy(
            update={"requested_enrichments": (GoalEnrichment.FLOW_CONTEXT,)}
        ),
        priority=1,
    ).job
    monkeypatch.setattr(
        handlers_module,
        "ensure_current_symbol_ready",
        lambda *_args, **_kwargs: pytest.fail("unsupported enrichment called provider"),
    )
    result = ProvisioningWorker(
        queue,
        worker_id="unsupported-enrichment",
        warehouse_path=tmp_path / "unsupported-enrichment.duckdb",
        handlers=(CurrentSymbolGoalHandler(),),
    ).process_one()
    assert result is not None
    assert result.error == (
        "UNSUPPORTED_ENRICHMENT_REQUEST; BLOCKED: current-symbol-provision"
    )
    assert queue.get(submitted.job_id).status is ProvisioningJobStatus.FAILED


def _assert_current_symbol_result_retains_tail_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = ProvisioningQueue(tmp_path / "tail-evidence.sqlite3")
    queue.initialize()
    submitted = queue.submit_or_join(current_goal("FPT"), priority=1).job
    ready_result = CurrentSymbolReadyResult(
        symbol="FPT",
        outcome=ProvisioningOutcome.READY,
        correlation_id="tail-correlation",
        requested_date="2026-01-07",
        resolved_date="2026-01-07",
        actions=(
            ProvisioningAction(
                action="sync_ohlcv",
                status="SUCCESS",
                dataset="equity.ohlcv",
                symbol="FPT",
                start_date="2026-01-06",
                end_date="2026-01-07",
                source="fixture",
                ingestion_run_id="fixture-run",
            ),
        ),
        reused_fresh_data=False,
        refreshed=False,
        warnings=(),
        errors=(),
    )
    monkeypatch.setattr(
        handlers_module,
        "ensure_current_symbol_ready",
        lambda *_args, **_kwargs: ready_result,
    )
    completed = ProvisioningWorker(
        queue,
        worker_id="tail-evidence",
        warehouse_path=tmp_path / "tail-evidence.duckdb",
        handlers=(CurrentSymbolGoalHandler(),),
    ).process_one()
    assert completed is not None
    assert completed.status is ProvisioningJobStatus.SUCCEEDED
    assert completed.result is not None
    assert json.loads(completed.result) == ready_result.to_trace_dict()
    assert queue.get(submitted.job_id).result == completed.result


def _assert_cancellation_stops_before_next_stage(tmp_path: Path) -> None:
    queue = ProvisioningQueue(tmp_path / "cancel-boundary.sqlite3")
    queue.initialize()
    submitted = queue.submit_or_join(current_goal("SSI"), priority=1).job

    def cancel_after_first_stage(
        connection: duckdb.DuckDBPyConnection | None,
    ) -> HandlerResult:
        assert connection is not None
        connection.execute("CREATE TABLE cancellation_boundary(value INTEGER)")
        queue.cancel(submitted.job_id)
        return HandlerResult(True, "FIRST_STAGE_COMPLETE")

    def second_stage(_: duckdb.DuckDBPyConnection | None) -> HandlerResult:
        raise AssertionError("cancellation must stop the next stage")

    result = ProvisioningWorker(
        queue,
        worker_id="cancelling",
        warehouse_path=tmp_path / "cancel-boundary.duckdb",
        handlers=(
            StagedHandler(
                (
                    stage("first", True, cancel_after_first_stage),
                    stage("second", False, second_stage),
                )
            ),
        ),
    ).process_one()
    assert result is not None
    assert result.status is ProvisioningJobStatus.CANCELLED


def _assert_terminalization_cancellation_races(tmp_path: Path) -> None:
    completion_queue = CancelBeforeCompletionQueue(tmp_path / "completion-race.sqlite3")
    completion_queue.initialize()
    completion_queue.submit_or_join(current_goal("VNM"), priority=1)
    success = StagedHandler(
        (stage("success", False, lambda _: HandlerResult(True, "success")),)
    )
    result = ProvisioningWorker(
        completion_queue, worker_id="completion-race", handlers=(success,)
    ).process_one()
    assert result is not None
    assert result.status is ProvisioningJobStatus.CANCELLED

    failure_queue = CancelBeforeFailureQueue(tmp_path / "failure-race.sqlite3")
    failure_queue.initialize()
    failure_queue.submit_or_join(range_goal("VN30"), priority=1)
    failure = ProvisioningWorker(
        failure_queue, worker_id="failure-race", handlers=()
    ).process_one()
    assert failure is not None
    assert failure.status is ProvisioningJobStatus.CANCELLED


def _assert_timing_configuration_is_bounded(tmp_path: Path) -> None:
    queue = ProvisioningQueue(tmp_path / "short-lease.sqlite3", lease_seconds=2)
    with pytest.raises(ProvisioningWorkerConfigurationError):
        ProvisioningWorker(
            queue,
            worker_id="invalid-lease",
            settings=WorkerSettings(stage_timeout_seconds=1, lease_safety_seconds=1),
        )


def _assert_timeout_finishes_the_safe_boundary(tmp_path: Path) -> None:
    queue = ProvisioningQueue(tmp_path / "overrun.sqlite3", lease_seconds=3)
    queue.initialize()
    queue.submit_or_join(current_goal("VCB"), priority=1)
    stage_started = Event()
    release_stage = Event()

    def overrun(connection: duckdb.DuckDBPyConnection | None) -> HandlerResult:
        assert connection is not None
        connection.execute("CREATE TABLE overrun_effect(value INTEGER)")
        connection.execute("INSERT INTO overrun_effect VALUES (1)")
        stage_started.set()
        assert release_stage.wait(timeout=5)
        return HandlerResult(True, "late success")

    worker = ProvisioningWorker(
        queue,
        worker_id="overrun",
        warehouse_path=tmp_path / "overrun.duckdb",
        handlers=(StagedHandler((stage("overrun", True, overrun),)),),
        settings=WorkerSettings(stage_timeout_seconds=1, lease_safety_seconds=1),
    )
    results: list[object] = []
    thread = Thread(target=lambda: results.append(worker.process_one()))
    thread.start()
    assert stage_started.wait(timeout=2)
    sleep(3.2)
    assert not queue.requeue_expired()
    release_stage.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    result = results[0]
    assert result is not None
    assert result.status is ProvisioningJobStatus.FAILED
    assert result.error == "STAGE_TIMEOUT"


def _assert_signal_stop_leaves_current_job_recoverable(tmp_path: Path) -> None:
    queue = ProvisioningQueue(tmp_path / "signal.sqlite3")
    queue.initialize()
    first = queue.submit_or_join(current_goal("ACB"), priority=2).job
    second = queue.submit_or_join(current_goal("VIC"), priority=1).job
    stage_started = Event()
    release_stage = Event()

    def first_stage(_: duckdb.DuckDBPyConnection | None) -> HandlerResult:
        stage_started.set()
        assert release_stage.wait(timeout=5)
        return HandlerResult(True, "FIRST_SAFE_BOUNDARY")

    def second_stage(_: duckdb.DuckDBPyConnection | None) -> HandlerResult:
        raise AssertionError("SIGTERM must stop before the next stage")

    worker = ProvisioningWorker(
        queue,
        worker_id="signal-worker",
        handlers=(
            StagedHandler(
                (
                    stage("first", False, first_stage),
                    stage("second", False, second_stage),
                )
            ),
        ),
    )
    thread = Thread(target=worker.process_one)
    thread.start()
    assert stage_started.wait(timeout=2)
    with worker.shutdown_signals():
        signal.raise_signal(signal.SIGTERM)
    release_stage.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert queue.get(first.job_id).status is ProvisioningJobStatus.RUNNING
    assert queue.get(second.job_id).status is ProvisioningJobStatus.QUEUED
