from __future__ import annotations

import duckdb
import pytest

from vnalpha.sandbox.contracts import SandboxFilesystemPolicy, SandboxOutputSchema
from vnalpha.sandbox.models import (
    SandboxJobId,
    SandboxJobRequest,
    SandboxJobStatus,
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


def test_repository_persists_rejection_and_failure_reasons() -> None:
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
        }
    )
    rejected_job = request.into_job(
        job_id=SandboxJobId("job-002"), run_id=SandboxRunId("run-001")
    )
    failed_job = request.into_job(
        job_id=SandboxJobId("job-003"), run_id=SandboxRunId("run-001")
    )

    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        repository.create(rejected_job)
        repository.create(failed_job)

        repository.mark_rejected(rejected_job.job_id, "approval is required")
        repository.mark_failed(failed_job.job_id, "runner unavailable")

        rejected = repository.get(rejected_job.job_id)
        failed = repository.get(failed_job.job_id)

    assert rejected is not None
    assert rejected.status.value == "rejected"
    assert rejected.rejection_reason == "approval is required"
    assert failed is not None
    assert failed.status.value == "failed"
    assert failed.failure_reason == "runner unavailable"


@pytest.mark.parametrize(
    ("status", "cpu_millis", "memory_mb", "timeout_seconds"),
    (
        ("invalid", 1, 16, 1),
        ("queued", 0, 16, 1),
        ("queued", 1, 0, 1),
        ("queued", 1, 16, 0),
    ),
)
def test_migration_rejects_invalid_sandbox_job_constraints(
    status: str, cpu_millis: int, memory_mb: int, timeout_seconds: int
) -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        with pytest.raises(duckdb.ConstraintException):
            _ = conn.execute(
                """
                INSERT INTO sandbox_job (
                    job_id, run_id, correlation_id, purpose, code_digest, status,
                    cpu_millis, memory_mb, timeout_seconds, network_enabled,
                    filesystem_policy_json, output_artifacts
                ) VALUES (?, 'run', 'correlation', 'purpose', 'digest', ?, ?, ?, ?, FALSE, ?, ?)
                """,
                [
                    "job",
                    status,
                    cpu_millis,
                    memory_mb,
                    timeout_seconds,
                    _DEFAULT_FILESYSTEM_POLICY_JSON,
                    _DEFAULT_OUTPUT_ARTIFACTS,
                ],
            )


@pytest.mark.parametrize("status", tuple(status.value for status in SandboxJobStatus))
def test_migration_accepts_each_declared_sandbox_job_status(status: str) -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        _ = conn.execute(
            """
            INSERT INTO sandbox_job (
                job_id, run_id, correlation_id, purpose, code_digest, status,
                cpu_millis, memory_mb, timeout_seconds, network_enabled,
                filesystem_policy_json, output_artifacts
            ) VALUES (?, 'run', 'correlation', 'purpose', 'digest', ?, 1, 16, 1, FALSE, ?, ?)
            """,
            [
                f"job-{status}",
                status,
                _DEFAULT_FILESYSTEM_POLICY_JSON,
                _DEFAULT_OUTPUT_ARTIFACTS,
            ],
        )


def test_repository_returns_missing_and_lists_only_safe_metadata() -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    request = SandboxJobRequest.model_validate(
        {
            "purpose": "evaluate candidate signal",
            "code": "secret = 'must-not-persist'",
            "correlation_id": "research-42",
            "resource_limits": {
                "cpu_millis": 500,
                "memory_mb": 128,
                "timeout_seconds": 10,
            },
        }
    )
    job = request.into_job(
        job_id=SandboxJobId("job-004"), run_id=SandboxRunId("run-001")
    )

    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)

        assert repository.get(SandboxJobId("missing")) is None
        assert repository.list() == ()

        repository.create(job)
        with pytest.raises(duckdb.BinderException):
            _ = conn.execute("SELECT code FROM sandbox_job")

        records = repository.list()

    assert records[0].code_digest == job.code_digest
