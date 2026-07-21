from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from types import TracebackType
from typing import Iterator

from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningQueueError,
)
from vnalpha.provisioning_queue.repository import ProvisioningQueue


class LeaseHeartbeat:
    def __init__(
        self,
        queue: ProvisioningQueue,
        job: ProvisioningJob,
        worker_id: str,
        interval_seconds: float,
    ) -> None:
        self._queue = queue
        self._job = job
        self._worker_id = worker_id
        self._interval_seconds = interval_seconds
        self._stopped = Event()
        self._failure: ProvisioningQueueError | None = None
        self._thread: Thread | None = None

    def __enter__(self) -> LeaseHeartbeat:
        self._queue.heartbeat(self._job.job_id, self._worker_id)
        self._thread = Thread(target=self._maintain, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        _: BaseException | None,
        __: TracebackType | None,
    ) -> bool:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join()
        if exception_type is None and self._failure is not None:
            raise self._failure
        return False

    def _maintain(self) -> None:
        while not self._stopped.wait(self._interval_seconds):
            try:
                self._queue.heartbeat(self._job.job_id, self._worker_id)
            except ProvisioningQueueError as error:
                self._failure = error
                self._stopped.set()
                return


class ExclusiveProvisioner:
    def __init__(self, queue_path: Path) -> None:
        self._lock_path = queue_path.with_suffix(queue_path.suffix + ".worker.lock")

    @contextmanager
    def hold(self) -> Iterator[None]:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            self._lock_path,
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
