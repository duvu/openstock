"""Typed, immutable sandbox-job values and request parsing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import (
    Annotated,
    ClassVar,
    Final,
    Literal,
    NewType,
    assert_never,
    final,
)

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import override

from vnalpha.sandbox.contracts import (
    ApprovedReadPath as ApprovedInputPath,
)
from vnalpha.sandbox.contracts import (
    SandboxFilesystemPolicy,
    SandboxJobValidationError,
    SandboxOutputSchema,
    parse_approved_read_path,
    validate_approved_read_paths,
)

SandboxJobId = NewType("SandboxJobId", str)
SandboxRunId = NewType("SandboxRunId", str)
SandboxCorrelationId = NewType("SandboxCorrelationId", str)
SandboxJobDetail = NewType("SandboxJobDetail", str)
MAX_SANDBOX_JOB_DETAIL_LENGTH: Final = 1_000
MAX_SANDBOX_PURPOSE_LENGTH: Final = 200
MAX_SANDBOX_CORRELATION_ID_LENGTH: Final = 128


@final
@dataclass(frozen=True, slots=True)
class SandboxJobNotFoundError(ValueError):
    """A requested sandbox job does not exist."""

    job_id: SandboxJobId

    @override
    def __str__(self) -> str:
        return f"sandbox job not found: {self.job_id}"


@final
@dataclass(frozen=True, slots=True)
class SandboxJobTransitionError(ValueError):
    """A sandbox job cannot move from its current state to a terminal state."""

    job_id: SandboxJobId
    status: SandboxJobStatus

    @override
    def __str__(self) -> str:
        return f"sandbox job {self.job_id} cannot transition from {self.status.value}"


class SandboxJobStatus(StrEnum):
    """Lifecycle states persisted for a sandbox job."""

    QUEUED = "queued"
    VALIDATING = "validating"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class SandboxResourceLimits(BaseModel):
    """Bounded execution resources captured with a job request."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    cpu_millis: Annotated[int, Field(ge=1, le=4_000)]
    memory_mb: Annotated[int, Field(ge=16, le=4_096)]
    timeout_seconds: Annotated[int, Field(ge=1, le=300)]


class SandboxJobRequest(BaseModel):
    """Untrusted sandbox request parsed into safe immutable values."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    purpose: Annotated[str, Field(min_length=1, max_length=200)]
    code: Annotated[str, Field(min_length=1, max_length=50_000)]
    correlation_id: Annotated[str, Field(min_length=1, max_length=128)]
    resource_limits: SandboxResourceLimits
    network_enabled: Literal[False] = False
    approved_input_paths: tuple[ApprovedInputPath, ...] = ()

    @field_validator("purpose", "correlation_id")
    @classmethod
    def _validate_metadata(cls, value: str) -> str:
        return _parse_sandbox_metadata(value)

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        if "\x00" in value:
            raise SandboxJobValidationError("code", "must not contain NUL bytes")
        return value

    @field_validator("approved_input_paths")
    @classmethod
    def _validate_input_paths(
        cls, values: tuple[ApprovedInputPath, ...]
    ) -> tuple[ApprovedInputPath, ...]:
        return tuple(parse_approved_read_path(value) for value in values)

    def into_job(self, *, job_id: SandboxJobId, run_id: SandboxRunId) -> SandboxJob:
        """Bind validated request content to the generated run-scoped identifiers."""

        return SandboxJob(
            job_id=job_id,
            run_id=run_id,
            purpose=self.purpose,
            code=self.code,
            correlation_id=SandboxCorrelationId(self.correlation_id),
            resource_limits=self.resource_limits,
            network_enabled=self.network_enabled,
            filesystem_policy=SandboxFilesystemPolicy(
                approved_read_paths=self.approved_input_paths
            ),
        )


@final
@dataclass(frozen=True, slots=True)
class SandboxJob:
    """A validated job whose code remains in memory until a future runner uses it."""

    job_id: SandboxJobId
    run_id: SandboxRunId
    purpose: str
    code: str
    correlation_id: SandboxCorrelationId
    resource_limits: SandboxResourceLimits
    network_enabled: Literal[False]
    filesystem_policy: SandboxFilesystemPolicy
    output_schema: SandboxOutputSchema = SandboxOutputSchema()
    status: SandboxJobStatus = SandboxJobStatus.QUEUED

    @property
    def code_digest(self) -> str:
        """Return the durable identifier for code without persisting its contents."""

        return sha256(self.code.encode("utf-8")).hexdigest()

    @property
    def approved_input_paths(self) -> tuple[ApprovedInputPath, ...]:
        """Expose legacy read paths derived from the authoritative policy."""

        return self.filesystem_policy.approved_read_paths

    @property
    def is_terminal(self) -> bool:
        """Report whether no further runtime lifecycle work is expected."""

        match self.status:
            case (
                SandboxJobStatus.QUEUED
                | SandboxJobStatus.VALIDATING
                | SandboxJobStatus.RUNNING
            ):
                return False
            case (
                SandboxJobStatus.SUCCEEDED
                | SandboxJobStatus.FAILED
                | SandboxJobStatus.REJECTED
                | SandboxJobStatus.CANCELLED
            ):
                return True
            case _ as unreachable:
                assert_never(unreachable)


def _parse_sandbox_metadata(value: str) -> str:
    normalized = value.strip()
    if not normalized or any(character in normalized for character in "\r\n\x00"):
        raise SandboxJobValidationError("metadata", "must be a single non-empty line")
    return normalized


def parse_sandbox_job_detail(value: str) -> SandboxJobDetail:
    """Parse a bounded user-controlled terminal detail at the persistence boundary."""

    if not value.strip() or len(value) > MAX_SANDBOX_JOB_DETAIL_LENGTH:
        raise SandboxJobValidationError(
            "terminal_detail",
            f"must contain 1 to {MAX_SANDBOX_JOB_DETAIL_LENGTH} non-blank characters",
        )
    return SandboxJobDetail(value)


def validate_sandbox_job(job: SandboxJob) -> None:
    """Validate direct domain construction before durable persistence."""

    match job.status:
        case SandboxJobStatus.QUEUED:
            pass
        case (
            SandboxJobStatus.VALIDATING
            | SandboxJobStatus.RUNNING
            | SandboxJobStatus.SUCCEEDED
            | SandboxJobStatus.FAILED
            | SandboxJobStatus.REJECTED
            | SandboxJobStatus.CANCELLED
        ):
            raise SandboxJobValidationError("status", "must be queued on creation")
        case _ as unreachable:
            assert_never(unreachable)
    if len(job.purpose) > MAX_SANDBOX_PURPOSE_LENGTH:
        raise SandboxJobValidationError("purpose", "must be a bounded non-empty line")
    if _parse_sandbox_metadata(job.purpose) != job.purpose:
        raise SandboxJobValidationError("purpose", "must be canonical")
    if len(job.correlation_id) > MAX_SANDBOX_CORRELATION_ID_LENGTH:
        raise SandboxJobValidationError(
            "correlation_id", "must be a bounded non-empty line"
        )
    if _parse_sandbox_metadata(job.correlation_id) != job.correlation_id:
        raise SandboxJobValidationError("correlation_id", "must be canonical")
    _ = validate_approved_read_paths(job.filesystem_policy.approved_read_paths)
    _ = SandboxFilesystemPolicy.model_validate(job.filesystem_policy.model_dump())
    _ = SandboxOutputSchema.model_validate(job.output_schema.model_dump())
