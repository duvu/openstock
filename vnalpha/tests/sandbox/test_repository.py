from __future__ import annotations

from vnalpha.sandbox.contracts import SandboxFilesystemPolicy
from vnalpha.sandbox.models import (
    SandboxJobId,
    SandboxJobRequest,
    SandboxRunId,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

_DEFAULT_FILESYSTEM_POLICY_JSON = SandboxFilesystemPolicy().model_dump_json()
_DEFAULT_OUTPUT_ARTIFACTS = [
    {
        "kind": "result",
        "path": "output/result.json",
        "media_type": "application/json",
    },
    {
        "kind": "summary",
        "path": "output/summary.md",
        "media_type": "text/markdown",
    },
]


def test_repository_persists_safe_metadata_and_terminal_states() -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    request = SandboxJobRequest.model_validate(
        {
            "purpose": "evaluate candidate signal",
            "code": "result = 1",
            "correlation_id": "research-42",
            "resource_limits": {
                "cpu_millis": 500,
                "memory_mb": 128,
                "timeout_seconds": 10,
            },
            "network_enabled": False,
            "approved_input_paths": ("inputs/candidate.json",),
        }
    )
    job = request.into_job(
        job_id=SandboxJobId("job-001"), run_id=SandboxRunId("run-001")
    )

    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)

        repository.create(job)
        repository.mark_succeeded(SandboxJobId("job-001"), "one result")

        stored = repository.get(SandboxJobId("job-001"))
        matching = repository.list_by_correlation(job.correlation_id)

    assert stored is not None
    assert stored.job_id == SandboxJobId("job-001")
    assert stored.status.value == "succeeded"
    assert stored.code_digest == job.code_digest
    assert stored.result_summary == "one result"
    assert matching == (stored,)
