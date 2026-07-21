from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import final

import pytest

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.artifact_manifest import SandboxArtifactManifest
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.contracts import SandboxFilesystemPolicy, SandboxOutputSchema
from vnalpha.sandbox.docker_orchestration import (
    SandboxDockerOrchestrationRequest,
    SandboxDockerOrchestrationStatus,
    SandboxDockerOrchestrator,
)
from vnalpha.sandbox.docker_runner import (
    DockerExecutionRequest,
    DockerExecutionResult,
    parse_docker_image_reference,
)
from vnalpha.sandbox.execution_evidence import SandboxExecutionEvidence
from vnalpha.sandbox.models import SandboxJob, SandboxJobId, SandboxJobStatus
from vnalpha.sandbox.output_validation import (
    SandboxOutputValidationResult,
    SandboxOutputValidator,
)
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
class _OutputFile:
    path: str
    content: bytes


@final
class _OutputWritingRunner:
    def __init__(
        self,
        output_path: Path,
        output_files: tuple[_OutputFile, ...],
        result: DockerExecutionResult,
        events: list[str],
    ) -> None:
        self._output_path = output_path
        self._output_files = output_files
        self._result = result
        self._events = events
        self.calls: list[DockerExecutionRequest] = []

    def run(self, request: DockerExecutionRequest) -> DockerExecutionResult:
        assert request.output_path == self._output_path
        self.calls.append(request)
        self._events.append("runner")
        for output_file in self._output_files:
            path = self._output_path.parent / output_file.path
            path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_bytes(output_file.content)
        return self._result


def _storage(tmp_path: Path, job: SandboxJob) -> SandboxArtifactStorage:
    return SandboxArtifactStorage(
        RunContext(
            run_id=str(job.run_id), surface="test", actor="pytest", log_root=tmp_path
        ),
        job.job_id,
    )


@pytest.fixture
def repository() -> Iterator[SandboxJobRepository]:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        yield SandboxJobRepository(conn)


def _job(*, with_optional_outputs: bool = False) -> SandboxJob:
    from vnalpha.sandbox.models import (
        SandboxCorrelationId,
        SandboxJobId,
        SandboxResourceLimits,
        SandboxRunId,
    )

    job = SandboxJob(
        job_id=SandboxJobId("terminalization-job"),
        run_id=SandboxRunId("terminalization-run"),
        purpose="validate canonical sandbox output",
        code="1 + 1\n",
        correlation_id=SandboxCorrelationId("terminalization-correlation"),
        resource_limits=SandboxResourceLimits(
            cpu_millis=250, memory_mb=128, timeout_seconds=30
        ),
        network_enabled=False,
        filesystem_policy=SandboxFilesystemPolicy(),
    )
    if not with_optional_outputs:
        return job
    return replace(
        job,
        output_schema=SandboxOutputSchema.model_validate(
            {
                "artifacts": (
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
                    {
                        "kind": "chart",
                        "path": "output/charts/chart.png",
                        "media_type": "image/png",
                    },
                    {
                        "kind": "table",
                        "path": "output/tables/table.csv",
                        "media_type": "text/csv",
                    },
                )
            }
        ),
    )


def _valid_outputs(*, with_optional_outputs: bool = False) -> tuple[_OutputFile, ...]:
    artifacts = ""
    optional_files: tuple[_OutputFile, ...] = ()
    if with_optional_outputs:
        artifacts = (
            ', "artifacts": [{"kind": "chart", "path": "output/charts/chart.png"}, '
            '{"kind": "table", "path": "output/tables/table.csv"}]'
        )
        optional_files = (
            _OutputFile("output/charts/chart.png", b"chart"),
            _OutputFile("output/tables/table.csv", b"table"),
        )
    else:
        artifacts = ', "artifacts": []'
    return (
        _OutputFile(
            "output/result.json",
            f'{{"schema_version": 1, "summary": "validated result"{artifacts}}}'.encode(),
        ),
        _OutputFile("output/summary.md", b"validated summary\n"),
        *optional_files,
    )


def _execute(
    *,
    tmp_path: Path,
    repository: SandboxJobRepository,
    output_files: tuple[_OutputFile, ...],
    result: DockerExecutionResult | None = None,
    with_optional_outputs: bool = False,
    configure: Callable[
        [
            SandboxJob,
            SandboxArtifactStorage,
            SandboxArtifactWriter,
            SandboxOutputValidator,
        ],
        None,
    ]
    | None = None,
) -> tuple[SandboxDockerOrchestrationStatus, str | None, SandboxJob, list[str], Path]:
    job = _job(with_optional_outputs=with_optional_outputs)
    repository.create(job)
    guard = SandboxStaticGuard.evaluate(job.code)
    events: list[str] = []
    with _storage(tmp_path, job) as storage:
        writer = SandboxArtifactWriter(storage)
        writer.persist_request(job)
        writer.persist_guard(guard)
        validator = SandboxOutputValidator(storage)
        if configure is not None:
            configure(job, storage, writer, validator)
        orchestrator = SandboxDockerOrchestrator(
            storage,
            writer,
            _OutputWritingRunner(
                storage.path_for("output"),
                output_files,
                DockerExecutionResult(return_code=0, stdout=b"out", stderr=b"err")
                if result is None
                else result,
                events,
            ),
            validator,
            repository,
        )
        outcome = orchestrator.execute(
            SandboxDockerOrchestrationRequest(job=job, guard_result=guard, image=_IMAGE)
        )
        return outcome.status, outcome.failure_code, job, events, storage.job_dir


def test_zero_exit_validated_outputs_persist_succeeded_after_finalization(
    tmp_path: Path, repository: SandboxJobRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    events: list[str] = []
    persist_execution = SandboxArtifactWriter.persist_execution
    validate = SandboxOutputValidator.validate
    finalize = SandboxArtifactWriter.persist_validation_and_manifest
    mark_succeeded = repository.mark_succeeded

    def record_execution(
        self: SandboxArtifactWriter, evidence: SandboxExecutionEvidence
    ) -> None:
        events.append("execution")
        persist_execution(self, evidence)

    def record_validation(
        self: SandboxOutputValidator, output_schema: SandboxOutputSchema
    ) -> SandboxOutputValidationResult:
        events.append("validation")
        return validate(self, output_schema)

    def record_finalization(
        self: SandboxArtifactWriter,
        validation: SandboxOutputValidationResult,
        output_schema: SandboxOutputSchema,
    ) -> SandboxArtifactManifest:
        events.append("finalization")
        return finalize(self, validation, output_schema)

    def record_success(job_id: SandboxJobId, summary: str) -> None:
        events.append("succeeded")
        mark_succeeded(job_id, summary)

    monkeypatch.setattr(SandboxArtifactWriter, "persist_execution", record_execution)
    monkeypatch.setattr(SandboxOutputValidator, "validate", record_validation)
    monkeypatch.setattr(
        SandboxArtifactWriter, "persist_validation_and_manifest", record_finalization
    )
    monkeypatch.setattr(repository, "mark_succeeded", record_success)

    # When
    status, failure_code, job, runner_events, job_dir = _execute(
        tmp_path=tmp_path,
        repository=repository,
        output_files=_valid_outputs(with_optional_outputs=True),
        with_optional_outputs=True,
    )

    # Then
    assert status is SandboxDockerOrchestrationStatus.SUCCEEDED
    assert failure_code is None
    assert runner_events == ["runner"]
    assert events == ["execution", "validation", "finalization", "succeeded"]
    assert (job_dir / "execution.json").exists()
    assert (job_dir / "validation.json").exists()
    assert (job_dir / "manifest.json").exists()
    stored = repository.get(job.job_id)
    assert stored is not None
    assert stored.status is SandboxJobStatus.SUCCEEDED
    assert stored.result_summary == "validated result"
