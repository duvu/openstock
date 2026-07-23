from __future__ import annotations

from enum import StrEnum
from os import getenv
from time import monotonic, sleep
from typing import Final

from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobNotFoundError,
)
from vnalpha.provisioning_queue.repository import ProvisioningQueue

DEFAULT_CURRENT_SYMBOL_WAIT_TIMEOUT_SECONDS: Final = 30.0
MAX_CURRENT_SYMBOL_WAIT_TIMEOUT_SECONDS: Final = 300.0
_CURRENT_SYMBOL_WAIT_TIMEOUT_ENV: Final = "VNALPHA_CURRENT_SYMBOL_WAIT_TIMEOUT_SECONDS"


class CurrentSymbolWaitMode(StrEnum):
    DETACH = "DETACH"
    WAIT_UP_TO = "WAIT_UP_TO"
    WAIT_UNTIL_TERMINAL = "WAIT_UNTIL_TERMINAL"


def default_current_symbol_wait_timeout_seconds() -> float:
    """Return the bounded interactive wait default from environment configuration."""

    configured = getenv(_CURRENT_SYMBOL_WAIT_TIMEOUT_ENV, "").strip()
    if not configured:
        return DEFAULT_CURRENT_SYMBOL_WAIT_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(configured)
    except ValueError as error:
        raise ValueError(
            f"{_CURRENT_SYMBOL_WAIT_TIMEOUT_ENV} must be a number"
        ) from error
    if not 0 <= timeout_seconds <= MAX_CURRENT_SYMBOL_WAIT_TIMEOUT_SECONDS:
        raise ValueError(
            f"{_CURRENT_SYMBOL_WAIT_TIMEOUT_ENV} must be between 0 and "
            f"{MAX_CURRENT_SYMBOL_WAIT_TIMEOUT_SECONDS:g}"
        )
    return timeout_seconds


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
