from __future__ import annotations

from enum import StrEnum
from time import monotonic, sleep

from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobNotFoundError,
)
from vnalpha.provisioning_queue.repository import ProvisioningQueue


class CurrentSymbolWaitMode(StrEnum):
    DETACH = "DETACH"
    WAIT_UP_TO = "WAIT_UP_TO"
    WAIT_UNTIL_TERMINAL = "WAIT_UNTIL_TERMINAL"


def wait_for_terminal(
    queue: ProvisioningQueue,
    job: ProvisioningJob,
    mode: CurrentSymbolWaitMode,
    timeout_seconds: float,
) -> ProvisioningJob:
    if timeout_seconds < 0:
        raise ValueError("queue wait timeout must not be negative")
    if mode is CurrentSymbolWaitMode.DETACH:
        return job
    deadline = monotonic() + timeout_seconds
    current = job
    while not current.is_terminal:
        if mode is CurrentSymbolWaitMode.WAIT_UP_TO and monotonic() >= deadline:
            return current
        sleep(0.1)
        job_id = current.job_id
        current = queue.get(job_id)
        if current is None:
            raise ProvisioningJobNotFoundError(job_id)
    return current
