"""Typed result-envelope and evidence values for output validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Literal, TypeAlias, final, override

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from vnalpha.sandbox.artifact_manifest import SandboxArtifactManifestEntry
from vnalpha.sandbox.contracts import MAX_OUTPUT_ARTIFACTS, ExpectedArtifactPath
from vnalpha.sandbox.models import MAX_SANDBOX_JOB_DETAIL_LENGTH

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


class SandboxOutputValidationStatus(StrEnum):
    """The controller's output-contract result."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SandboxOutputValidationFailureCode(StrEnum):
    """Safe, durable validation failure categories."""

    MISSING_ARTIFACT = "missing_artifact"
    UNSAFE_ARTIFACT = "unsafe_artifact"
    ARTIFACT_TOO_LARGE = "artifact_too_large"
    INVALID_RESULT = "invalid_result"
    INVALID_SUMMARY = "invalid_summary"
    ARTIFACT_REFERENCE_MISMATCH = "artifact_reference_mismatch"


@final
@dataclass(frozen=True, slots=True)
class _InvalidJsonError(ValueError):
    @override
    def __str__(self) -> str:
        return "invalid result JSON"


@final
@dataclass(frozen=True, slots=True)
class _InvalidResultEnvelopeError(ValueError):
    @override
    def __str__(self) -> str:
        return "invalid result envelope"


class SandboxResultArtifactReference(BaseModel):
    """One closed chart or table reference declared by the result envelope."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    kind: Literal["chart", "table"]
    path: ExpectedArtifactPath


class SandboxResultEnvelope(BaseModel):
    """Extensible top-level result contract with a strict required envelope."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="allow", strict=True
    )

    schema_version: int
    summary: str = Field(min_length=1, max_length=MAX_SANDBOX_JOB_DETAIL_LENGTH)
    artifacts: tuple[SandboxResultArtifactReference, ...] = Field(
        max_length=MAX_OUTPUT_ARTIFACTS - 2, strict=False
    )

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != 1:
            raise _InvalidResultEnvelopeError()
        return value

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        if not value.strip():
            raise _InvalidResultEnvelopeError()
        return value

    @field_validator("artifacts")
    @classmethod
    def _validate_references(
        cls, values: tuple[SandboxResultArtifactReference, ...]
    ) -> tuple[SandboxResultArtifactReference, ...]:
        paths = tuple(reference.path for reference in values)
        if len(paths) != len(set(paths)):
            raise _InvalidResultEnvelopeError()
        return values


@final
@dataclass(frozen=True, slots=True)
class SandboxOutputValidationEvidence:
    """Safe, canonical validation evidence suitable for durable persistence."""

    status: SandboxOutputValidationStatus
    failure_code: SandboxOutputValidationFailureCode | None
    artifact_path: str | None
    detail: str
    validated_paths: tuple[str, ...]

    def to_json_bytes(self) -> bytes:
        """Serialize stable UTF-8 evidence without untrusted output values."""

        payload = {
            "artifact_path": self.artifact_path,
            "detail": self.detail,
            "failure_code": self.failure_code,
            "schema_version": 1,
            "status": self.status,
            "validated_paths": self.validated_paths,
        }
        return (
            json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            + "\n"
        ).encode("utf-8")


@final
@dataclass(frozen=True, slots=True)
class SandboxOutputValidationResult:
    """The parsed result on success plus inventory for safely observed artifacts."""

    evidence: SandboxOutputValidationEvidence
    result: SandboxResultEnvelope | None
    inventory: tuple[SandboxArtifactManifestEntry, ...]

    @property
    def succeeded(self) -> bool:
        """Return whether all declared canonical outputs passed validation."""

        return self.evidence.status is SandboxOutputValidationStatus.SUCCEEDED


def parse_result(content: bytes) -> SandboxResultEnvelope | None:
    """Strictly parse the untrusted canonical result object."""

    try:
        decoded = content.decode("utf-8")
        _assert_strict_json_syntax(decoded)
        return SandboxResultEnvelope.model_validate_json(content)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        _InvalidJsonError,
    ):
        return None


def _assert_strict_json_syntax(decoded: str) -> None:
    json.loads(
        decoded,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonfinite_number,
    )


def _reject_duplicate_keys(
    pairs: list[tuple[str, JsonValue]],
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidJsonError()
        result[key] = value
    return result


def _reject_nonfinite_number(_: str) -> None:
    raise _InvalidJsonError()
