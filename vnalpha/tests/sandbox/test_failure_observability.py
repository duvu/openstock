from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import final

import duckdb

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.contracts import ApprovedReadPath, SandboxFilesystemPolicy
from vnalpha.sandbox.docker_orchestration import (
    SandboxDockerOrchestrationFailureCode,
    SandboxDockerOrchestrationRequest,
    SandboxDockerOrchestrationStatus,
    SandboxDockerOrchestrator,
)
from vnalpha.sandbox.docker_runner import (
    DockerExecutionRequest,
    DockerExecutionResult,
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

_IMAGE = parse_docker_image_reference(
    f"registry.example/openstock/sandbox@sha256:{'a' * 64}"
)
_SECRET = "TOKEN=super-secret"


@final
@dataclass(frozen=True, slots=True)
class _RecordedRequest:
    request: DockerExecutionRequest


@final
class _FakeRunner:
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
        job_id=SandboxJobId("job-observability"),
        run_id=SandboxRunId("run-observability"),
        purpose="evaluate a reference dataset",
        code="1 + 1\n",
        correlation_id=SandboxCorrelationId("job-correlation-id"),
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
        RunContext(
            run_id="run-observability",
            surface="test",
            actor="pytest",
            log_root=tmp_path,
        ),
        SandboxJobId("job-observability"),
    )


def _repository() -> SandboxJobRepository:
    return SandboxJobRepository(duckdb.connect(":memory:"))


def _execute(
    storage: SandboxArtifactStorage, execution: DockerExecutionResult
) -> tuple[SandboxDockerOrchestrationStatus, str | None]:
    job = _job()
    guard = SandboxStaticGuard.evaluate(job.code)
    writer = SandboxArtifactWriter(storage)
    writer.persist_request(job)
    writer.persist_guard(guard)
    runner = _FakeRunner(execution, storage.path_for("output"))
    result = SandboxDockerOrchestrator(
        storage, writer, runner, SandboxOutputValidator(storage), _repository()
    ).execute(
        SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
    )
    return result.status, result.failure_code


def _error_records(storage: SandboxArtifactStorage) -> list[dict[str, str]]:
    errors_path = storage.job_dir.parent.parent / "errors.jsonl"
    return [json.loads(line) for line in errors_path.read_text().splitlines()]


def test_records_invalid_runner_contract_failure(tmp_path: Path) -> None:
    # Given
    execution = DockerExecutionResult(return_code=1, stdout=b"partial", stderr=b"bad")
    with _storage(tmp_path) as storage:
        # When
        status, recorded_failure_code = _execute(storage, execution)

        # Then
        assert status is SandboxDockerOrchestrationStatus.FAILED
        assert (
            recorded_failure_code
            == SandboxDockerOrchestrationFailureCode.INVALID_RUNNER_RESULT
        )
        record = _error_records(storage)[0]
        assert record["error_type"] == "SandboxDockerRunnerContractFailure"
        assert record["failure_code"] == "invalid_runner_result"
