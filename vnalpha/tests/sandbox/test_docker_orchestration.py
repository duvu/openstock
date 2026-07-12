from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
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


def test_execute_rejects_guard_digest_mismatch_before_output_or_runner(
    tmp_path: Path, repository: SandboxJobRepository
) -> None:
    from vnalpha.sandbox.docker_orchestration import (
        SandboxDockerOrchestrationFailureCode,
        SandboxDockerOrchestrationRequest,
        SandboxDockerOrchestrationStatus,
        SandboxDockerOrchestrator,
    )

    # Given
    job = _job()
    mismatch = SandboxStaticGuard.evaluate("2 + 2\n")
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        runner = _RecordingRunner(
            DockerExecutionResult(return_code=0, stdout=b"", stderr=b""),
            storage.path_for("output"),
        )

        # When
        result = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        ).execute(
            SandboxDockerOrchestrationRequest(
                job=job, guard_result=mismatch, image=_IMAGE
            )
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.REJECTED
        assert (
            result.failure_code
            is SandboxDockerOrchestrationFailureCode.GUARD_DIGEST_MISMATCH
        )
        assert runner.calls == []
        assert not (storage.job_dir / "output").exists()
        assert not (storage.job_dir / "execution.json").exists()


def test_execute_rejects_denied_guard_before_output_or_runner(
    tmp_path: Path, repository: SandboxJobRepository
) -> None:
    from vnalpha.sandbox.docker_orchestration import (
        SandboxDockerOrchestrationFailureCode,
        SandboxDockerOrchestrationRequest,
        SandboxDockerOrchestrationStatus,
        SandboxDockerOrchestrator,
    )

    # Given
    job = replace(_job(), code="__import__('os')")
    denied = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(denied)
        runner = _RecordingRunner(
            DockerExecutionResult(return_code=0, stdout=b"", stderr=b""),
            storage.path_for("output"),
        )

        # When
        result = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        ).execute(
            SandboxDockerOrchestrationRequest(
                job=job, guard_result=denied, image=_IMAGE
            )
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.REJECTED
        assert result.failure_code is SandboxDockerOrchestrationFailureCode.GUARD_DENIED
        assert runner.calls == []
        assert not (storage.job_dir / "output").exists()
        assert not (storage.job_dir / "execution.json").exists()
        assert (storage.job_dir / "guard.json").read_bytes() == denied.to_json_bytes()


def test_execute_rejects_allowed_guard_forged_after_denial_was_persisted(
    tmp_path: Path, repository: SandboxJobRepository
) -> None:
    from vnalpha.sandbox.docker_orchestration import (
        SandboxDockerOrchestrationFailureCode,
        SandboxDockerOrchestrationRequest,
        SandboxDockerOrchestrationStatus,
        SandboxDockerOrchestrator,
    )

    # Given
    job = replace(_job(), code="__import__('os')")
    denied = SandboxStaticGuard.evaluate(job.code)
    forged_allowed = replace(denied, allowed=True, violations=())
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(denied)
        runner = _RecordingRunner(
            DockerExecutionResult(return_code=0, stdout=b"", stderr=b""),
            storage.path_for("output"),
        )

        # When
        result = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        ).execute(
            SandboxDockerOrchestrationRequest(
                job=job, guard_result=forged_allowed, image=_IMAGE
            )
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.REJECTED
        assert (
            result.failure_code
            is SandboxDockerOrchestrationFailureCode.GUARD_EVIDENCE_MISMATCH
        )
        assert runner.calls == []
        assert not (storage.job_dir / "output").exists()
        assert not (storage.job_dir / "execution.json").exists()


def test_execute_rejects_unpersisted_guard_before_output_or_runner(
    tmp_path: Path, repository: SandboxJobRepository
) -> None:
    from vnalpha.sandbox.docker_orchestration import (
        SandboxDockerOrchestrationFailureCode,
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
        runner = _RecordingRunner(
            DockerExecutionResult(return_code=0, stdout=b"", stderr=b""),
            storage.path_for("output"),
        )

        # When
        result = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        ).execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.REJECTED
        assert (
            result.failure_code
            is SandboxDockerOrchestrationFailureCode.GUARD_NOT_PERSISTED
        )
        assert runner.calls == []
        assert not (storage.job_dir / "output").exists()
        assert not (storage.job_dir / "execution.json").exists()


def test_execute_persists_typed_runtime_failure(
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
    execution = DockerExecutionResult(
        return_code=-1,
        stdout=b"partial output",
        stderr=b"timed out",
        failure_code=DockerFailureCode.RUNTIME_TIMEOUT,
        detail="Docker execution timed out",
        stdout_truncated=True,
        stderr_truncated=False,
        cleanup_succeeded=False,
    )
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(guard)
        runner = _RecordingRunner(execution, storage.path_for("output"))

        # When
        result = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        ).execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.FAILED
        assert result.failure_code is DockerFailureCode.RUNTIME_TIMEOUT
        assert (storage.job_dir / "output/stdout.txt").read_bytes() == b"partial output"
        assert (storage.job_dir / "output/stderr.txt").read_bytes() == b"timed out"


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
def test_execute_persists_preflight_failure_as_rejected(
    tmp_path: Path, failure_code: DockerFailureCode, repository: SandboxJobRepository
) -> None:
    from vnalpha.sandbox.docker_orchestration import (
        SandboxDockerOrchestrationRequest,
        SandboxDockerOrchestrationStatus,
        SandboxDockerOrchestrator,
    )

    # Given
    job = _job()
    guard = SandboxStaticGuard.evaluate(job.code)
    execution = DockerExecutionResult(
        return_code=-1,
        stdout=b"",
        stderr=b"preflight failure",
        failure_code=failure_code,
        detail="Docker preflight failed",
    )
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(guard)
        runner = _RecordingRunner(execution, storage.path_for("output"))

        # When
        result = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        ).execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.REJECTED
        assert result.failure_code is failure_code
        assert len(runner.calls) == 1
        assert (
            f'"failure_code": "{failure_code.value}"'.encode()
            in (storage.job_dir / "execution.json").read_bytes()
        )
        assert (
            storage.job_dir / "output/stderr.txt"
        ).read_bytes() == b"preflight failure"


def test_execute_persists_invalid_runner_result_as_failed(
    tmp_path: Path, repository: SandboxJobRepository
) -> None:
    from vnalpha.sandbox.docker_orchestration import (
        SandboxDockerOrchestrationFailureCode,
        SandboxDockerOrchestrationRequest,
        SandboxDockerOrchestrationStatus,
        SandboxDockerOrchestrator,
    )

    # Given
    job = _job()
    guard = SandboxStaticGuard.evaluate(job.code)
    execution = DockerExecutionResult(return_code=1, stdout=b"partial", stderr=b"bad")
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(guard)
        runner = _RecordingRunner(execution, storage.path_for("output"))

        # When
        result = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        ).execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.FAILED
        assert (
            result.failure_code
            is SandboxDockerOrchestrationFailureCode.INVALID_RUNNER_RESULT
        )
        assert (
            b'"failure_code": "invalid_runner_result"'
            in (storage.job_dir / "execution.json").read_bytes()
        )
        assert (storage.job_dir / "output/stdout.txt").read_bytes() == b"partial"
        assert (storage.job_dir / "output/stderr.txt").read_bytes() == b"bad"


def test_execute_fails_when_execution_evidence_persistence_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: SandboxJobRepository
) -> None:
    from vnalpha.sandbox.docker_orchestration import (
        SandboxDockerOrchestrationFailureCode,
        SandboxDockerOrchestrationRequest,
        SandboxDockerOrchestrationStatus,
        SandboxDockerOrchestrator,
    )
    from vnalpha.sandbox.storage import SandboxArtifactPathError

    # Given
    job = _job()
    guard = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(guard)
        runner = _RecordingRunner(
            DockerExecutionResult(return_code=0, stdout=b"out", stderr=b"err"),
            storage.path_for("output"),
        )
        write_atomic_bytes = storage.write_atomic_bytes

        def reject_stdout(path: str, content: bytes) -> Path:
            if path == "output/stdout.txt":
                raise SandboxArtifactPathError(path)
            return write_atomic_bytes(path, content)

        monkeypatch.setattr(storage, "write_atomic_bytes", reject_stdout)

        # When
        result = SandboxDockerOrchestrator(
            storage, writer, runner, SandboxOutputValidator(storage), repository
        ).execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )

        # Then
        assert result.status is SandboxDockerOrchestrationStatus.FAILED
        assert (
            result.failure_code
            is SandboxDockerOrchestrationFailureCode.ARTIFACT_PERSISTENCE_FAILED
        )
        assert len(runner.calls) == 1
        assert not (storage.job_dir / "execution.json").exists()
