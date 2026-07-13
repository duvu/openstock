from __future__ import annotations

import json
from dataclasses import dataclass
from typing import ClassVar

import duckdb
from pydantic import BaseModel, ConfigDict

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.docker_policy import DockerImageReference
from vnalpha.sandbox.docker_runner import parse_docker_image_reference
from vnalpha.sandbox.execution_errors import SandboxExecutionError
from vnalpha.sandbox.execution_types import JsonValue
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxJobStatus,
    SandboxJobTransitionError,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.repository import SandboxJobRecord, SandboxJobRepository
from vnalpha.sandbox.storage import SandboxArtifactStorage

_MAX_REQUEST_BYTES = 32_768
_MAX_CODE_BYTES = 65_536
_MAX_INPUT_REFERENCE_BYTES = 16_384


class _RetainedArguments(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    purpose: str
    job_id: str
    run_id: str
    correlation_id: str
    code_digest: str
    input_references: tuple[str, ...]
    resource_limits: SandboxResourceLimits
    image: str


class _RetainedRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    purpose: str
    correlation_id: str
    resource_limits: SandboxResourceLimits
    network_enabled: bool


class _RetainedReferences(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    approved_read_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetainedBindingRequest:
    conn: duckdb.DuckDBPyConnection
    arguments: dict[str, JsonValue]
    run_context: RunContext
    default_image: DockerImageReference


@dataclass(frozen=True, slots=True)
class RetainedSandboxJob:
    job: SandboxJob
    image: DockerImageReference


@dataclass(frozen=True, slots=True)
class _BindingState:
    record: SandboxJobRecord
    job: SandboxJob
    arguments: _RetainedArguments
    references: _RetainedReferences


def load_retained_sandbox_job(request: RetainedBindingRequest) -> RetainedSandboxJob:
    arguments = _RetainedArguments.model_validate(request.arguments)
    job_id = SandboxJobId(arguments.job_id)
    run_id = SandboxRunId(arguments.run_id)
    record = SandboxJobRepository(request.conn).get(job_id)
    if record is None:
        raise SandboxExecutionError(f"sandbox job not found: {job_id}")
    if record.status is not SandboxJobStatus.QUEUED:
        raise SandboxJobTransitionError(job_id, record.status)
    storage_context = _context_for_run(request.run_context, run_id)
    with SandboxArtifactStorage(storage_context, job_id) as storage:
        retained_request = _RetainedRequest.model_validate_json(
            storage.read_bounded_regular_file(
                "request.json", max_bytes=_MAX_REQUEST_BYTES
            )
        )
        code = storage.read_bounded_regular_file(
            "generated_code.py", max_bytes=_MAX_CODE_BYTES
        ).decode("utf-8")
        references = _RetainedReferences.model_validate(
            json.loads(
                storage.read_bounded_regular_file(
                    "inputs/references.json", max_bytes=_MAX_INPUT_REFERENCE_BYTES
                )
            )
        )
    job = SandboxJob(
        job_id=job_id,
        run_id=run_id,
        purpose=retained_request.purpose,
        code=code,
        correlation_id=SandboxCorrelationId(retained_request.correlation_id),
        resource_limits=retained_request.resource_limits,
        network_enabled=retained_request.network_enabled,
        filesystem_policy=record.filesystem_policy,
        output_schema=record.output_schema,
        status=record.status,
    )
    _assert_binding(
        _BindingState(
            record=record,
            job=job,
            arguments=arguments,
            references=references,
        )
    )
    image = (
        request.default_image
        if arguments.image == str(request.default_image)
        else parse_docker_image_reference(arguments.image)
    )
    return RetainedSandboxJob(job=job, image=image)


def _context_for_run(current: RunContext, run_id: SandboxRunId) -> RunContext:
    if current.run_id == str(run_id):
        return current
    return RunContext(
        run_id=str(run_id),
        surface=current.surface,
        actor=current.actor,
        log_root=current.log_root,
    )


def _assert_binding(state: _BindingState) -> None:
    record = state.record
    job = state.job
    arguments = state.arguments
    references = state.references
    expected_references = tuple(job.filesystem_policy.approved_read_paths)
    if (
        record.code_digest != job.code_digest
        or arguments.code_digest != job.code_digest
    ):
        raise SandboxExecutionError("sandbox job digest mismatch")
    if arguments.purpose != job.purpose:
        raise SandboxExecutionError("sandbox purpose binding changed")
    if arguments.correlation_id != str(job.correlation_id):
        raise SandboxExecutionError("sandbox correlation binding changed")
    if arguments.input_references != expected_references:
        raise SandboxExecutionError("sandbox input binding changed")
    if references.approved_read_paths != expected_references:
        raise SandboxExecutionError("sandbox retained input references changed")
    if arguments.resource_limits != job.resource_limits:
        raise SandboxExecutionError("sandbox resource binding changed")
