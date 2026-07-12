from __future__ import annotations

import builtins
from collections.abc import Iterator
from pathlib import Path
from typing import Never

import duckdb
import pytest

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, CommandStatus
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.docker_orchestration import SandboxDockerOrchestrator
from vnalpha.sandbox.docker_runtime import DockerRunner
from vnalpha.sandbox.models import SandboxJob, SandboxJobId, SandboxJobRequest, SandboxRunId
from vnalpha.sandbox.repository import SandboxJobRepository
from vnalpha.sandbox.static_guard import SandboxStaticGuard
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def sandbox_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxJobRepository(conn)
        for job_id in ("job-001", "job-002"):
            job = _sandbox_job(job_id)
            repository.create(job)
        _ = conn.execute(
            "UPDATE sandbox_job SET created_at = TIMESTAMP '2026-07-12 00:00:00'"
        )
        yield conn


def _sandbox_job(job_id: str) -> SandboxJob:
    request = SandboxJobRequest.model_validate(
        {
            "purpose": f"research {job_id}",
            "code": "secret = 'sandbox-secret-must-not-leak'",
            "correlation_id": "research-42",
            "resource_limits": {
                "cpu_millis": 500,
                "memory_mb": 128,
                "timeout_seconds": 10,
            },
        }
    )
    return request.into_job(job_id=SandboxJobId(job_id), run_id=SandboxRunId("run-001"))


def _execute(command_text: str, conn: duckdb.DuckDBPyConnection) -> CommandResult:
    return build_default_registry().execute(parse(command_text), conn=conn)


def _execution_must_not_start(*_args: Never, **_kwargs: Never) -> Never:
    pytest.fail("/sandbox run must not start sandbox execution")


def _block_execution_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SandboxJobRepository, "create", _execution_must_not_start)
    monkeypatch.setattr(SandboxStaticGuard, "evaluate", _execution_must_not_start)
    monkeypatch.setattr(SandboxArtifactWriter, "__init__", _execution_must_not_start)
    monkeypatch.setattr(SandboxDockerOrchestrator, "execute", _execution_must_not_start)
    monkeypatch.setattr(DockerRunner, "run", _execution_must_not_start)


def test_sandbox_is_registered_when_command_surface_is_available() -> None:
    # Given: the default command registry
    registry = build_default_registry()

    # When: its names are inspected
    names = registry.names()

    # Then: the sandbox command is discoverable
    assert "sandbox" in names


def test_sandbox_run_requires_explicit_approval_without_starting_execution(
    sandbox_connection: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: every sandbox execution boundary rejects invocation
    _block_execution_boundaries(monkeypatch)

    # When: a nonempty purpose requests sandbox execution
    result = _execute("/sandbox run compare persisted datasets", sandbox_connection)

    # Then: approval is required and execution never starts
    assert result.status is CommandStatus.VALIDATION_ERROR
    assert result.summary is not None
    assert "approval is required" in result.summary.lower()
    assert "not started" in result.summary.lower()


def test_sandbox_run_rejects_missing_purpose(
    sandbox_connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a migrated warehouse
    # When: run has no purpose
    # Then: the command reports a validation error
    with pytest.raises(CommandValidationError, match="purpose"):
        _ = _execute("/sandbox run", sandbox_connection)


def test_sandbox_status_returns_safe_persisted_metadata(
    sandbox_connection: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a real persisted sandbox job containing generated-code secret text
    _block_execution_boundaries(monkeypatch)

    # When: its status is requested
    result = _execute("/sandbox status job-001", sandbox_connection)

    # Then: metadata is returned without code or secret leakage
    assert result.status is CommandStatus.SUCCESS
    assert "job-001" in str(result)
    assert "sandbox-secret-must-not-leak" not in str(result)


@pytest.mark.parametrize(
    "command_text",
    (
        "/sandbox status",
        "/sandbox status job-001 extra",
        "/sandbox status job-001 --latest",
        "/sandbox status job-001 status=queued",
    ),
)
def test_sandbox_status_requires_exactly_one_job_id(
    command_text: str, sandbox_connection: duckdb.DuckDBPyConnection
) -> None:
    # Given: a migrated warehouse
    # When: status receives malformed arguments
    # Then: the command rejects them inline
    with pytest.raises(CommandValidationError):
        _ = _execute(command_text, sandbox_connection)


def test_sandbox_status_returns_empty_result_for_missing_job(
    sandbox_connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a warehouse without the requested job
    # When: status targets that job ID
    result = _execute("/sandbox status missing-job", sandbox_connection)

    # Then: the result is empty rather than an execution attempt
    assert result.status is CommandStatus.EMPTY_RESULT


def test_sandbox_artifact_returns_canonical_metadata_without_filesystem_access(
    sandbox_connection: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a persisted job and filesystem methods that reject access
    _block_execution_boundaries(monkeypatch)
    monkeypatch.setattr(Path, "mkdir", _execution_must_not_start)
    monkeypatch.setattr(Path, "open", _execution_must_not_start)
    monkeypatch.setattr(Path, "read_bytes", _execution_must_not_start)
    monkeypatch.setattr(Path, "read_text", _execution_must_not_start)
    monkeypatch.setattr(builtins, "open", _execution_must_not_start)

    # When: canonical artifact metadata is requested
    result = _execute("/sandbox artifact job-001", sandbox_connection)

    # Then: only canonical path metadata is returned
    assert result.status is CommandStatus.SUCCESS
    rendered = str(result)
    assert "runs/run-001/sandbox/job-001" in rendered
    assert "manifest.json" in rendered
    assert "sandbox-secret-must-not-leak" not in rendered


def test_sandbox_artifact_returns_empty_result_for_missing_job(
    sandbox_connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a warehouse without the requested job
    # When: canonical artifact metadata targets that job ID
    result = _execute("/sandbox artifact missing-job", sandbox_connection)

    # Then: the command reports an empty result
    assert result.status is CommandStatus.EMPTY_RESULT


@pytest.mark.parametrize(
    "command_text",
    (
        "/sandbox artifact",
        "/sandbox artifact job-001 extra",
        "/sandbox artifact job-001 --latest",
        "/sandbox list",
        "/sandbox list --latest value",
        "/sandbox list --latest extra",
        "/sandbox list --latest status=queued",
        "/sandbox list --unknown",
        "/sandbox inspect job-001",
    ),
)
def test_sandbox_rejects_unsupported_or_noncanonical_query_forms(
    command_text: str, sandbox_connection: duckdb.DuckDBPyConnection
) -> None:
    # Given: a migrated warehouse
    # When: an unsupported or noncanonical query form is used
    # Then: the command reports validation rather than broadening its surface
    with pytest.raises(CommandValidationError):
        _ = _execute(command_text, sandbox_connection)


def test_sandbox_list_latest_selects_deterministic_newest_record(
    sandbox_connection: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: two records with the same creation time and different IDs
    _block_execution_boundaries(monkeypatch)

    # When: the latest record is requested
    result = _execute("/sandbox list --latest", sandbox_connection)

    # Then: descending job ID breaks the timestamp tie deterministically
    assert result.status is CommandStatus.SUCCESS
    assert "job-002" in str(result)
    assert "job-001" not in str(result)


def test_sandbox_list_latest_returns_empty_result_when_no_jobs_exist() -> None:
    # Given: a migrated warehouse with no sandbox jobs
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        # When: the latest record is requested
        result = _execute("/sandbox list --latest", conn)

    # Then: the command returns an empty result
    assert result.status is CommandStatus.EMPTY_RESULT
