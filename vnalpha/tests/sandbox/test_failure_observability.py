from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import final

import duckdb
import pytest

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
from vnalpha.sandbox.storage import SandboxArtifactPathError, SandboxArtifactStorage

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


@pytest.mark.parametrize(
    "failure_code",
    (
        DockerFailureCode.HOST_NOT_LINUX,
        DockerFailureCode.DOCKER_LAUNCH_FAILED,
        DockerFailureCode.DOCKER_NOT_FOUND,
        DockerFailureCode.DAEMON_UNAVAILABLE,
        DockerFailureCode.DAEMON_TIMEOUT,
        DockerFailureCode.SERVER_NOT_LINUX,
        DockerFailureCode.IMAGE_NOT_AVAILABLE,
        DockerFailureCode.IMAGE_PROBE_TIMEOUT,
    ),
)
def test_records_redacted_metadata_for_every_docker_preflight_failure(
    tmp_path: Path, failure_code: DockerFailureCode, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    monkeypatch.setenv("VNALPHA_LOG_CONTENT_MODE", "full")
    execution = DockerExecutionResult(
        return_code=-1,
        stdout=_SECRET.encode(),
        stderr=b"--env SECRET=super-secret",
        failure_code=failure_code,
        detail=f"{_SECRET} /home/user/private/input.csv",
    )
    with _storage(tmp_path) as storage:
        # When
        status, recorded_failure_code = _execute(storage, execution)

        # Then
        assert status is SandboxDockerOrchestrationStatus.REJECTED
        assert recorded_failure_code == failure_code
        records = _error_records(storage)
        assert len(records) == 1
        record = records[0]
        assert record["correlation_id"] == "job-correlation-id"
        assert record["event_type"] == "EXCEPTION_CAPTURED"
        assert record["job_id"] == "job-observability"
        assert record["status"] == "rejected"
        assert record["failure_code"] == failure_code.value
        assert record["runtime_kind"] == "docker"
        serialized_record = json.dumps(record)
        assert _SECRET not in serialized_record
        assert "input.csv" not in serialized_record
        assert "stdout" not in serialized_record
        assert "stderr" not in serialized_record


@pytest.mark.parametrize(
    "failure_code",
    (DockerFailureCode.RUNTIME_TIMEOUT, DockerFailureCode.RUNTIME_FAILED),
)
def test_records_redacted_metadata_for_every_docker_runtime_failure(
    tmp_path: Path, failure_code: DockerFailureCode
) -> None:
    # Given
    execution = DockerExecutionResult(
        return_code=-1,
        stdout=_SECRET.encode(),
        stderr=b"runtime failure",
        failure_code=failure_code,
        detail=_SECRET,
    )
    with _storage(tmp_path) as storage:
        # When
        status, recorded_failure_code = _execute(storage, execution)

        # Then
        assert status is SandboxDockerOrchestrationStatus.FAILED
        assert recorded_failure_code == failure_code
        record = _error_records(storage)[0]
        assert record["error_type"] == "SandboxDockerRuntimeFailure"
        assert _SECRET not in json.dumps(record)


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


def test_records_evidence_persistence_failure_without_exception_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    job = _job()
    guard = SandboxStaticGuard.evaluate(job.code)
    execution = DockerExecutionResult(return_code=0, stdout=b"out", stderr=b"err")
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(guard)
        write_atomic_bytes = storage.write_atomic_bytes

        def reject_stdout(path: str, content: bytes) -> Path:
            if path == "output/stdout.txt":
                raise SandboxArtifactPathError(f"{path} {_SECRET}")
            return write_atomic_bytes(path, content)

        monkeypatch.setattr(storage, "write_atomic_bytes", reject_stdout)

        # When
        result = SandboxDockerOrchestrator(
            storage,
            writer,
            _FakeRunner(execution, storage.path_for("output")),
            SandboxOutputValidator(storage),
            _repository(),
        ).execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.FAILED
        assert (
            result.failure_code
            is SandboxDockerOrchestrationFailureCode.ARTIFACT_PERSISTENCE_FAILED
        )
        record = _error_records(storage)[0]
        assert record["error_type"] == "SandboxExecutionPersistenceFailure"
        assert _SECRET not in json.dumps(record)


def test_ignores_error_record_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    from vnalpha.sandbox import failure_observability

    def reject_append(_: Path, record: dict[str, str]) -> None:
        del record
        raise OSError("errors.jsonl unavailable")

    monkeypatch.setattr(failure_observability, "append_jsonl", reject_append)
    execution = DockerExecutionResult(
        return_code=-1,
        stdout=b"",
        stderr=b"",
        failure_code=DockerFailureCode.RUNTIME_FAILED,
    )
    with _storage(tmp_path) as storage:
        # When
        status, recorded_failure_code = _execute(storage, execution)

        # Then
        assert status is SandboxDockerOrchestrationStatus.FAILED
        assert recorded_failure_code is DockerFailureCode.RUNTIME_FAILED
        assert (storage.job_dir / "execution.json").exists()
        assert not (storage.job_dir.parent.parent / "errors.jsonl").exists()


def test_does_not_record_guard_policy_rejection(tmp_path: Path) -> None:
    # Given
    job = SandboxJob(
        job_id=SandboxJobId("job-observability"),
        run_id=SandboxRunId("run-observability"),
        purpose="evaluate a reference dataset",
        code="__import__('os')",
        correlation_id=SandboxCorrelationId("job-correlation-id"),
        resource_limits=SandboxResourceLimits(
            cpu_millis=250, memory_mb=128, timeout_seconds=30
        ),
        network_enabled=False,
        filesystem_policy=SandboxFilesystemPolicy(
            approved_read_paths=(ApprovedReadPath("inputs/reference.csv"),)
        ),
    )
    guard = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(guard)

        # When
        result = SandboxDockerOrchestrator(
            storage,
            writer,
            _FakeRunner(
                DockerExecutionResult(return_code=0, stdout=b"", stderr=b""),
                storage.path_for("output"),
            ),
            SandboxOutputValidator(storage),
            _repository(),
        ).execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.REJECTED
        assert result.failure_code is SandboxDockerOrchestrationFailureCode.GUARD_DENIED
        assert not (storage.job_dir.parent.parent / "errors.jsonl").exists()
