from __future__ import annotations

import pytest

from vnalpha.sandbox.models import (
    SandboxJob,
    SandboxJobId,
    SandboxJobNotFoundError,
    SandboxJobRequest,
    SandboxJobTransitionError,
    SandboxRunId,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


def _job(job_id: str) -> SandboxJob:
    request = SandboxJobRequest.model_validate(
        {
            "purpose": "evaluate",
            "code": "result = 1",
            "correlation_id": "quality-42",
            "resource_limits": {
                "cpu_millis": 500,
                "memory_mb": 128,
                "timeout_seconds": 10,
            },
        }
    )
    return request.into_job(job_id=SandboxJobId(job_id), run_id=SandboxRunId("run-001"))


def test_terminal_result_cannot_be_overwritten_and_missing_job_fails() -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    job = _job("job-001")
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        repository.create(job)
        repository.mark_succeeded(job.job_id, "complete")

        with pytest.raises(SandboxJobTransitionError):
            repository.mark_failed(job.job_id, "must not overwrite")
        with pytest.raises(SandboxJobNotFoundError):
            repository.mark_failed(SandboxJobId("missing"), "missing")

        stored = repository.get(job.job_id)

    assert stored is not None
    assert stored.status.value == "succeeded"
    assert stored.result_summary == "complete"
    assert stored.failure_reason is None
