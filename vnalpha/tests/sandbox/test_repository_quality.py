from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, assert_never

import duckdb
import pytest

from vnalpha.sandbox.contracts import (
    ApprovedReadPath as ApprovedInputPath,
)
from vnalpha.sandbox.contracts import (
    SandboxFilesystemPolicy,
    SandboxJobValidationError,
    SandboxOutputSchema,
)
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxJobNotFoundError,
    SandboxJobRequest,
    SandboxJobStatus,
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


@pytest.mark.parametrize("detail", ("", "x" * 1_001))
@pytest.mark.parametrize("operation", ("succeeded", "rejected", "failed"))
def test_terminal_details_are_rejected_at_repository_boundary(
    detail: str, operation: Literal["succeeded", "rejected", "failed"]
) -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    job = _job("job-001")
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        repository.create(job)

        with pytest.raises(ValueError):
            match operation:
                case "succeeded":
                    repository.mark_succeeded(job.job_id, detail)
                case "rejected":
                    repository.mark_rejected(job.job_id, detail)
                case "failed":
                    repository.mark_failed(job.job_id, detail)
                case _ as unreachable:
                    assert_never(unreachable)


@pytest.mark.parametrize(
    ("statement", "detail"),
    (
        ("UPDATE sandbox_job SET result_summary = ? WHERE job_id = 'job-001'", ""),
        ("UPDATE sandbox_job SET rejection_reason = ? WHERE job_id = 'job-001'", ""),
        ("UPDATE sandbox_job SET failure_reason = ? WHERE job_id = 'job-001'", ""),
        (
            "UPDATE sandbox_job SET result_summary = ? WHERE job_id = 'job-001'",
            "x" * 1_001,
        ),
        (
            "UPDATE sandbox_job SET rejection_reason = ? WHERE job_id = 'job-001'",
            "x" * 1_001,
        ),
        (
            "UPDATE sandbox_job SET failure_reason = ? WHERE job_id = 'job-001'",
            "x" * 1_001,
        ),
    ),
)
def test_terminal_details_are_rejected_by_database(statement: str, detail: str) -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    job = _job("job-001")
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        repository.create(job)

        with pytest.raises(duckdb.ConstraintException):
            _ = conn.execute(statement, [detail])


def test_repository_lists_ties_by_job_id() -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    first = _job("job-b")
    second = _job("job-a")
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        repository.create(first)
        repository.create(second)
        _ = conn.execute("UPDATE sandbox_job SET created_at = ?", [created_at])

        listed = repository.list()
        correlated = repository.list_by_correlation(first.correlation_id)

    assert tuple(record.job_id for record in listed) == (
        SandboxJobId("job-a"),
        SandboxJobId("job-b"),
    )
    assert tuple(record.job_id for record in correlated) == (
        SandboxJobId("job-a"),
        SandboxJobId("job-b"),
    )


def test_durable_metadata_is_rejected_at_repository_and_sql_boundaries() -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    job = _job("job-001")
    filesystem_policy_json = job.filesystem_policy.model_dump_json()
    output_artifacts = [
        {
            "kind": artifact.kind,
            "path": artifact.path,
            "media_type": artifact.media_type,
        }
        for artifact in job.output_schema.artifacts
    ]
    oversized_job = SandboxJob(
        job_id=job.job_id,
        run_id=job.run_id,
        purpose="x" * 201,
        code=job.code,
        correlation_id=job.correlation_id,
        resource_limits=job.resource_limits,
        network_enabled=job.network_enabled,
        filesystem_policy=job.filesystem_policy,
    )
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        with pytest.raises(ValueError):
            repository.create(oversized_job)
        with pytest.raises(duckdb.ConstraintException):
            _ = conn.execute(
                """
                INSERT INTO sandbox_job (
                    job_id, run_id, correlation_id, purpose, code_digest, status,
                    cpu_millis, memory_mb, timeout_seconds, network_enabled,
                    filesystem_policy_json, output_artifacts, result_summary
                ) VALUES ('job', 'run', ?, ?, 'digest', 'queued', 1, 16, 1, FALSE, ?, ?, '   ')
                """,
                ["x" * 129, "x" * 201, filesystem_policy_json, output_artifacts],
            )


@pytest.mark.parametrize(
    ("purpose", "correlation_id", "approved_input_paths"),
    (
        ("line\nbreak", "quality-42", ()),
        ("\x00", "quality-42", ()),
        ("evaluate", "line\nbreak", ()),
        ("evaluate", "\x00", ()),
        ("evaluate", "quality-42", (ApprovedInputPath("../escape"),)),
        ("evaluate", "quality-42", (ApprovedInputPath("/absolute"),)),
        ("  evaluate  ", "quality-42", ()),
        ("evaluate", "  quality-42  ", ()),
        ("evaluate", "quality-42", (ApprovedInputPath("inputs/./result.json"),)),
    ),
)
def test_direct_job_reuses_request_metadata_and_path_validation(
    purpose: str,
    correlation_id: str,
    approved_input_paths: tuple[ApprovedInputPath, ...],
) -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    job = _job("job-001")
    direct_job = SandboxJob(
        job_id=job.job_id,
        run_id=job.run_id,
        purpose=purpose,
        code=job.code,
        correlation_id=SandboxCorrelationId(correlation_id),
        resource_limits=job.resource_limits,
        network_enabled=job.network_enabled,
        filesystem_policy=SandboxFilesystemPolicy.model_construct(
            approved_read_paths=approved_input_paths,
            writable_directory="output",
        ),
    )
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        with pytest.raises(SandboxJobValidationError):
            repository.create(direct_job)
        assert repository.get(job.job_id) is None


@pytest.mark.parametrize(
    "status",
    (SandboxJobStatus.RUNNING, SandboxJobStatus.SUCCEEDED, SandboxJobStatus.CANCELLED),
)
def test_repository_rejects_direct_non_queued_jobs(status: SandboxJobStatus) -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    job = _job("job-001")
    non_queued_job = SandboxJob(
        job_id=job.job_id,
        run_id=job.run_id,
        purpose=job.purpose,
        code=job.code,
        correlation_id=job.correlation_id,
        resource_limits=job.resource_limits,
        network_enabled=job.network_enabled,
        filesystem_policy=job.filesystem_policy,
        status=status,
    )
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        with pytest.raises(SandboxJobValidationError):
            repository.create(non_queued_job)
        assert repository.get(job.job_id) is None


def test_repository_rejects_direct_job_with_invalid_writable_output_directory() -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    job = _job("job-001")
    invalid_job = SandboxJob(
        job_id=job.job_id,
        run_id=job.run_id,
        purpose=job.purpose,
        code=job.code,
        correlation_id=job.correlation_id,
        resource_limits=job.resource_limits,
        network_enabled=job.network_enabled,
        filesystem_policy=SandboxFilesystemPolicy.model_construct(
            approved_read_paths=(),
            writable_output_directory="other",
        ),
    )
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)

        with pytest.raises(ValueError):
            repository.create(invalid_job)

        assert repository.get(job.job_id) is None


def test_repository_rejects_direct_job_with_invalid_output_schema() -> None:
    from vnalpha.sandbox.repository import SandboxJobRepository

    job = _job("job-001")
    invalid_job = SandboxJob(
        job_id=job.job_id,
        run_id=job.run_id,
        purpose=job.purpose,
        code=job.code,
        correlation_id=job.correlation_id,
        resource_limits=job.resource_limits,
        network_enabled=job.network_enabled,
        filesystem_policy=job.filesystem_policy,
        output_schema=SandboxOutputSchema.model_construct(artifacts=()),
    )
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)

        with pytest.raises(ValueError):
            repository.create(invalid_job)

        assert repository.get(job.job_id) is None


def test_migration_backfills_legacy_paths_and_repository_round_trips_contracts() -> (
    None
):
    from vnalpha.sandbox.repository import SandboxJobRepository

    with in_memory_connection() as conn:
        _ = conn.execute(
            """
            CREATE TABLE sandbox_job (
                job_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                correlation_id VARCHAR NOT NULL,
                purpose VARCHAR NOT NULL,
                code_digest VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                cpu_millis INTEGER NOT NULL,
                memory_mb INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                network_enabled BOOLEAN NOT NULL,
                approved_input_paths_json VARCHAR NOT NULL,
                result_summary VARCHAR,
                rejection_reason VARCHAR,
                failure_reason VARCHAR
            )
            """
        )
        _ = conn.execute(
            """
            INSERT INTO sandbox_job (
                job_id, run_id, correlation_id, purpose, code_digest, status,
                cpu_millis, memory_mb, timeout_seconds, network_enabled,
                approved_input_paths_json
            ) VALUES ('legacy-job', 'legacy-run', 'legacy-correlation', 'evaluate',
                      'digest', 'queued', 1, 16, 1, FALSE, '["inputs/legacy.json"]')
            """
        )

        run_migrations(conn=conn)
        record = SandboxJobRepository(conn).get(SandboxJobId("legacy-job"))

    assert record is not None
    assert record.filesystem_policy.approved_read_paths == ("inputs/legacy.json",)
    assert tuple(artifact.path for artifact in record.output_schema.artifacts) == (
        "output/result.json",
        "output/summary.md",
    )
