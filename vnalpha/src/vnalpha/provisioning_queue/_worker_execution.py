from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from time import monotonic

from vnalpha.provisioning_queue._worker_runtime import LeaseHeartbeat
from vnalpha.provisioning_queue.handlers import (
    HandlerResult,
    ProvisioningGoalHandler,
    ProvisioningGoalStage,
)
from vnalpha.provisioning_queue.queue_models import ProvisioningJob
from vnalpha.provisioning_queue.repository import ProvisioningQueue
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

_NO_HANDLER_STAGES = "NO_HANDLER_STAGES"
_STAGE_TIMEOUT = "STAGE_TIMEOUT"


@dataclass(frozen=True, slots=True)
class HandlerCompleted:
    result: HandlerResult


@dataclass(frozen=True, slots=True)
class HandlerCancellationRequested:
    pass


@dataclass(frozen=True, slots=True)
class HandlerStopRequested:
    pass


HandlerExecution = (
    HandlerCompleted | HandlerCancellationRequested | HandlerStopRequested
)


def execute_handler_stages(
    *,
    queue: ProvisioningQueue,
    job: ProvisioningJob,
    worker_id: str,
    handler: ProvisioningGoalHandler,
    coordinator: WarehouseWriteCoordinator,
    stop_requested: Event,
    stage_timeout_seconds: int,
    lease_interval_seconds: float,
) -> HandlerExecution:
    stages = handler.stages(job.goal)
    if not stages:
        return HandlerCompleted(HandlerResult(False, _NO_HANDLER_STAGES))
    result = HandlerResult(False, _NO_HANDLER_STAGES)
    for index, stage in enumerate(stages):
        boundary = _safe_boundary(queue, job, stop_requested)
        if boundary is not None:
            return boundary
        started_at = monotonic()
        result = _execute_stage(
            queue=queue,
            job=job,
            worker_id=worker_id,
            stage=stage,
            coordinator=coordinator,
            lease_interval_seconds=lease_interval_seconds,
        )
        if monotonic() - started_at > stage_timeout_seconds:
            return HandlerCompleted(
                _failed_with_blocked(_STAGE_TIMEOUT, stages[index + 1 :])
            )
        if not result.succeeded:
            return HandlerCompleted(
                _failed_with_blocked(result.detail, stages[index + 1 :])
            )
    return HandlerCompleted(result)


def _failed_with_blocked(
    detail: str, dependent_stages: tuple[ProvisioningGoalStage, ...]
) -> HandlerResult:
    if not dependent_stages:
        return HandlerResult(False, detail)
    blocked = ", ".join(stage.name for stage in dependent_stages)
    return HandlerResult(False, f"{detail}; BLOCKED: {blocked}")


def _safe_boundary(
    queue: ProvisioningQueue, job: ProvisioningJob, stop_requested: Event
) -> HandlerCancellationRequested | HandlerStopRequested | None:
    current = queue.get(job.job_id)
    if current is not None and current.cancellation_requested:
        return HandlerCancellationRequested()
    if stop_requested.is_set():
        return HandlerStopRequested()
    return None


def _execute_stage(
    *,
    queue: ProvisioningQueue,
    job: ProvisioningJob,
    worker_id: str,
    stage: ProvisioningGoalStage,
    coordinator: WarehouseWriteCoordinator,
    lease_interval_seconds: float,
) -> HandlerResult:
    heartbeat = LeaseHeartbeat(queue, job, worker_id, lease_interval_seconds)
    if stage.requires_warehouse_write:
        with coordinator.transaction() as connection:
            with heartbeat:
                return stage.execute(connection)
    with heartbeat:
        return stage.execute(None)
