from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import final

import pytest

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.contracts import ApprovedReadPath, SandboxFilesystemPolicy
from vnalpha.sandbox.docker_runner import (
    DockerExecutionRequest,
    DockerExecutionResult,
    DockerFailureCode,
    parse_docker_image_reference,
)
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.output_validation import SandboxOutputValidator
from vnalpha.sandbox.repository import SandboxJobRepository
from vnalpha.sandbox.static_guard import SandboxStaticGuard
from vnalpha.sandbox.storage import SandboxArtifactStorage
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

_IMAGE = parse_docker_image_reference(
    f"registry.example/openstock/sandbox@sha256:{'a' * 64}"
)


@final
@dataclass(frozen=True, slots=True)
class _RecordedRequest:
    request: DockerExecutionRequest


@final
class _RecordingRunner:
    def __init__(self, result: DockerExecutionResult, output_path: Path) -> None:
        self._result = result
        self._output_path = output_path
        self.calls: list[_RecordedRequest] = []

    def run(self, request: DockerExecutionRequest) -> DockerExecutionResult:
        assert self._output_path.is_dir()
        self.calls.append(_RecordedRequest(request))
        return self._result


def _job() -> SandboxJob:
    return SandboxJob(
        job_id=SandboxJobId("job-001"),
        run_id=SandboxRunId("run-001"),
        purpose="evaluate a reference dataset",
        code="1 + 1\n",
        correlation_id=SandboxCorrelationId("correlation-001"),
        resource_limits=SandboxResourceLimits(
            cpu_millis=250, memory_mb=128, timeout_seconds=30
        ),
        network_enabled=False,
        filesystem_policy=SandboxFilesystemPolicy(
            approved_read_paths=(ApprovedReadPath("inputs/reference.csv"),)
        ),
    )


def _storage(tmp_path: Path) -> SandboxArtifactStorage:
    return SandboxArtifactStorage(
        RunContext(run_id="run-001", surface="test", actor="pytest", log_root=tmp_path),
        SandboxJobId("job-001"),
    )


@pytest.fixture
def repository() -> Iterator[SandboxJobRepository]:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        yield SandboxJobRepository(conn)


def test_execute_creates_canonical_output_then_runs_digest_bound_request(
    tmp_path: Path, repository: SandboxJobRepository
) -> None:
    from vnalpha.sandbox.docker_orchestration import (
        SandboxDockerOrchestrationRequest,
        SandboxDockerOrchestrationStatus,
        SandboxDockerOrchestrator,
    )

    # Given
    job = _job()
    guard = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(guard)
        input_path = storage.path_for("inputs/reference.csv")
        input_path.parent.mkdir(exist_ok=True)
        _ = input_path.write_text("reference\n")
        output_path = storage.path_for("output")
        runner = _RecordingRunner(
            DockerExecutionResult(
                return_code=-1,
                stdout=b"out",
                stderr=b"err",
                failure_code=DockerFailureCode.RUNTIME_FAILED,
            ),
            output_path,
        )
        orchestrator = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        )

        # When
        result = orchestrator.execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.FAILED
        assert len(runner.calls) == 1
        request = runner.calls[0].request
        assert request.image == _IMAGE
        assert request.code_path == storage.path_for("generated_code.py")
        assert request.input_paths == (input_path,)
        assert request.output_path == output_path
        assert request.resource_limits == job.resource_limits
        assert request.environment == ()
        assert (storage.job_dir / "output/stdout.txt").read_bytes() == b"out"
        assert (storage.job_dir / "output/stderr.txt").read_bytes() == b"err"
        assert not (storage.job_dir / "manifest.json").exists()
