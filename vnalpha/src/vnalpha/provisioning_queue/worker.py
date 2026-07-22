"""One lease-aware sequential worker for durable provisioning jobs."""

from __future__ import annotations

import signal
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, current_thread, main_thread
from types import FrameType
from typing import Callable, Final, Iterator, assert_never

from vnalpha.provisioning_queue._worker_execution import (
    HandlerCancellationRequested,
    HandlerCompleted,
    HandlerStopRequested,
    execute_handler_stages,
)
from vnalpha.provisioning_queue._worker_runtime import (
    ExclusiveProvisioner,
)
from vnalpha.provisioning_queue.handlers import (
    CurrentSymbolGoalHandler,
    ProvisioningGoalHandler,
)
from vnalpha.provisioning_queue.models import GoalType, goal_type
from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobLeaseError,
)
from vnalpha.provisioning_queue.repository import ProvisioningQueue
from vnalpha.warehouse.connection import WarehouseOpenError
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

MAX_CONCURRENCY: Final = 1
_CANCELLATION_REASON: Final = "CANCELLED_AT_SAFE_BOUNDARY"
_UNSUPPORTED_HANDLER: Final = "UNSUPPORTED_GOAL_HANDLER"


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    stage_timeout_seconds: int = 45
    lease_safety_seconds: int = 5
    idle_poll_seconds: float = 1.0


_DEFAULT_HANDLERS: Final[tuple[ProvisioningGoalHandler, ...]] = (
    CurrentSymbolGoalHandler(),
)
_DEFAULT_WORKER_SETTINGS: Final = WorkerSettings()


class ProvisioningWorkerConfigurationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class ProvisioningWorker:
    """Claim at most one job at a time and own its normal warehouse mutation."""

    max_concurrency: Final[int] = MAX_CONCURRENCY

    def __init__(
        self,
        queue: ProvisioningQueue,
        *,
        worker_id: str,
        warehouse_path: Path | str | None = None,
        handlers: tuple[ProvisioningGoalHandler, ...] = _DEFAULT_HANDLERS,
        settings: WorkerSettings = _DEFAULT_WORKER_SETTINGS,
    ) -> None:
        self._queue = queue
        self._worker_id = worker_id
        self._settings = settings
        self._coordinator = WarehouseWriteCoordinator(path=warehouse_path)
        self._stop_requested = Event()
        self._process_lock = Lock()
        self._handlers = _handler_registry(handlers)
        queue_settings = queue.initialize()
        self._provisioner_gate = ExclusiveProvisioner(queue.path.resolve())
        _validate_settings(settings, queue_settings.lease_seconds)

    def request_stop(self) -> None:
        """Stop future claims while allowing the current safe boundary to finish."""

        self._stop_requested.set()

    def process_one(self) -> ProvisioningJob | None:
        with self._process_lock:
            with self._provisioner_gate.hold():
                if self._stop_requested.is_set():
                    return None
                job = self._queue.claim(self._worker_id)
                if job is None:
                    return None
                return self._process_claimed(job)

    def run(self, *, once: bool = False) -> int:
        if once:
            return int(self.process_one() is not None)
        processed = 0
        while not self._stop_requested.is_set():
            if self.process_one() is None:
                self._stop_requested.wait(self._settings.idle_poll_seconds)
            else:
                processed += 1
        return processed

    @contextmanager
    def shutdown_signals(self) -> Iterator[None]:
        if current_thread() is not main_thread():
            yield
            return
        previous_int = signal.getsignal(signal.SIGINT)
        previous_term = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, _signal_stop(self))
        signal.signal(signal.SIGTERM, _signal_stop(self))
        try:
            yield
        finally:
            signal.signal(signal.SIGINT, previous_int)
            signal.signal(signal.SIGTERM, previous_term)

    def _process_claimed(self, job: ProvisioningJob) -> ProvisioningJob | None:
        handler = self._handlers.get(goal_type(job.goal))
        if handler is None:
            return self._fail_or_cancel(job, _UNSUPPORTED_HANDLER)
        if self._cancellation_requested(job):
            return self._cancel_at_safe_boundary(job)
        try:
            outcome = execute_handler_stages(
                queue=self._queue,
                job=job,
                worker_id=self._worker_id,
                handler=handler,
                coordinator=self._coordinator,
                stop_requested=self._stop_requested,
                stage_timeout_seconds=self._settings.stage_timeout_seconds,
                lease_interval_seconds=max(
                    0.25, self._settings.lease_safety_seconds / 2
                ),
            )
            match outcome:
                case HandlerCancellationRequested():
                    return self._cancel_at_safe_boundary(job)
                case HandlerStopRequested():
                    return None
                case HandlerCompleted(result=result):
                    if self._cancellation_requested(job):
                        return self._cancel_at_safe_boundary(job)
                    if self._stop_requested.is_set():
                        return None
                    self._queue.heartbeat(job.job_id, self._worker_id)
                    if result.succeeded:
                        return self._queue.complete(
                            job.job_id, self._worker_id, result.detail
                        )
                    return self._queue.fail(job.job_id, self._worker_id, result.detail)
                case unreachable:
                    assert_never(unreachable)
        except ProvisioningJobLeaseError:
            if self._cancellation_requested(job):
                return self._cancel_at_safe_boundary(job)
            return None
        except WarehouseOpenError as error:
            return self._fail_or_cancel(job, str(error))

    def _cancellation_requested(self, job: ProvisioningJob) -> bool:
        current = self._queue.get(job.job_id)
        return current is not None and current.cancellation_requested

    def _cancel_at_safe_boundary(self, job: ProvisioningJob) -> ProvisioningJob | None:
        try:
            return self._queue.acknowledge_cancellation(
                job.job_id, self._worker_id, _CANCELLATION_REASON
            )
        except ProvisioningJobLeaseError:
            return None

    def _fail_or_cancel(
        self, job: ProvisioningJob, detail: str
    ) -> ProvisioningJob | None:
        try:
            return self._queue.fail(job.job_id, self._worker_id, detail)
        except ProvisioningJobLeaseError:
            if self._cancellation_requested(job):
                return self._cancel_at_safe_boundary(job)
            return None


def _handler_registry(
    handlers: tuple[ProvisioningGoalHandler, ...],
) -> dict[GoalType, ProvisioningGoalHandler]:
    registry: dict[GoalType, ProvisioningGoalHandler] = {}
    for handler in handlers:
        if handler.goal_type in registry:
            raise ProvisioningWorkerConfigurationError("duplicate provisioning handler")
        registry[handler.goal_type] = handler
    return registry


def _validate_settings(settings: WorkerSettings, lease_seconds: int) -> None:
    if settings.stage_timeout_seconds < 1 or settings.lease_safety_seconds < 1:
        raise ProvisioningWorkerConfigurationError(
            "worker timing settings must be positive"
        )
    if settings.idle_poll_seconds <= 0:
        raise ProvisioningWorkerConfigurationError(
            "idle poll interval must be positive"
        )
    if settings.stage_timeout_seconds + settings.lease_safety_seconds >= lease_seconds:
        raise ProvisioningWorkerConfigurationError(
            "queue lease must exceed stage timeout plus safety margin"
        )


def _signal_stop(worker: ProvisioningWorker) -> Callable[[int, FrameType | None], None]:
    def request_stop(_: int, __: FrameType | None) -> None:
        worker.request_stop()

    return request_stop


__all__ = [
    "MAX_CONCURRENCY",
    "ProvisioningWorker",
    "ProvisioningWorkerConfigurationError",
    "WorkerSettings",
]
