"""Immutable filesystem and expected-output contracts for sandbox jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, ClassVar, Final, Literal, NewType, assert_never

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from typing_extensions import override

ApprovedReadPath = NewType("ApprovedReadPath", str)
ExpectedArtifactPath = NewType("ExpectedArtifactPath", str)
MAX_APPROVED_READ_PATHS: Final = 32
MAX_APPROVED_READ_PATHS_JSON_LENGTH: Final = 4_096
MAX_OUTPUT_ARTIFACTS: Final = 32
MAX_OUTPUT_ARTIFACT_PATH_LENGTH: Final = 1_024
MAX_OUTPUT_SCHEMA_JSON_LENGTH: Final = 8_192
OUTPUT_DIRECTORY: Final = "output"


@dataclass(frozen=True, slots=True)
class SandboxJobValidationError(ValueError):
    """A sandbox I/O contract violates the durable safety boundary."""

    field_name: str
    detail: str

    @override
    def __str__(self) -> str:
        return f"invalid sandbox {self.field_name}: {self.detail}"


def parse_approved_read_path(value: str) -> ApprovedReadPath:
    """Parse one canonical read-only path outside the output directory."""

    path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    is_safe = (
        bool(value)
        and not path.is_absolute()
        and not windows_path.is_absolute()
        and ".." not in path.parts
        and value != "."
        and "\\" not in value
        and path.as_posix() == value
        and not _is_output_path(path)
    )
    if not is_safe:
        raise SandboxJobValidationError(
            "approved_read_paths",
            "must be canonical, relative, traversal-free, and outside output",
        )
    return ApprovedReadPath(value)


def validate_approved_read_paths(
    values: tuple[ApprovedReadPath, ...],
) -> tuple[ApprovedReadPath, ...]:
    """Validate the complete canonical set of approved sandbox read paths."""

    parsed = tuple(parse_approved_read_path(value) for value in values)
    if len(parsed) > MAX_APPROVED_READ_PATHS:
        raise SandboxJobValidationError("approved_read_paths", "exceeds maximum count")
    if len(set(parsed)) != len(parsed):
        raise SandboxJobValidationError(
            "approved_read_paths", "must not contain duplicates"
        )
    return parsed


def _is_output_path(path: PurePosixPath) -> bool:
    return bool(path.parts) and path.parts[0] == OUTPUT_DIRECTORY


class SandboxFilesystemPolicy(BaseModel):
    """The sole authority for sandbox readable paths and writable directory."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    approved_read_paths: Annotated[
        tuple[ApprovedReadPath, ...], Field(max_length=MAX_APPROVED_READ_PATHS)
    ] = ()
    writable_output_directory: Literal["output"] = Field(
        default=OUTPUT_DIRECTORY,
        validation_alias=AliasChoices(
            "writable_output_directory", "writable_directory"
        ),
    )

    @property
    def writable_directory(self) -> Literal["output"]:
        """Expose the persisted compatibility name for the fixed output directory."""

        return self.writable_output_directory

    @field_validator("approved_read_paths")
    @classmethod
    def _validate_approved_read_paths(
        cls, values: tuple[ApprovedReadPath, ...]
    ) -> tuple[ApprovedReadPath, ...]:
        return validate_approved_read_paths(values)


class SandboxExpectedArtifact(BaseModel):
    """One artifact path and media type that a sandbox job may emit."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    kind: Literal["result", "summary", "chart", "table"]
    path: Annotated[
        ExpectedArtifactPath, Field(max_length=MAX_OUTPUT_ARTIFACT_PATH_LENGTH)
    ]
    media_type: str = Field(min_length=1)

    @field_validator("media_type")
    @classmethod
    def _validate_media_type(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise SandboxJobValidationError("media_type", "must not be blank")
        return normalized

    @model_validator(mode="after")
    def _validate_path_scope(self) -> SandboxExpectedArtifact:
        path = PurePosixPath(self.path)
        path_is_canonical = (
            bool(self.path)
            and not path.is_absolute()
            and not PureWindowsPath(self.path).is_absolute()
            and ".." not in path.parts
            and path.as_posix() == self.path
        )
        if not path_is_canonical:
            raise SandboxJobValidationError(
                "artifact.path", "must be canonical, relative, and traversal-free"
            )
        match self.kind:
            case "result":
                _require_artifact_path(self.path, "output/result.json")
                _require_media_type(self.media_type, "application/json")
            case "summary":
                _require_artifact_path(self.path, "output/summary.md")
                _require_media_type(self.media_type, "text/markdown")
            case "chart":
                _require_directory(self.path, "output/charts")
                _require_media_type(self.media_type, "image/png")
            case "table":
                _require_directory(self.path, "output/tables")
                _require_media_type(self.media_type, "text/csv")
            case unreachable:
                assert_never(unreachable)
        return self


def _require_artifact_path(path: ExpectedArtifactPath, expected: str) -> None:
    if path != expected:
        raise SandboxJobValidationError("artifact.path", f"must be {expected}")


def _require_media_type(media_type: str, expected: str) -> None:
    if media_type != expected:
        raise SandboxJobValidationError("media_type", f"must be {expected}")


def _require_directory(path: ExpectedArtifactPath, directory: str) -> None:
    if not path.startswith(f"{directory}/"):
        raise SandboxJobValidationError("artifact.path", f"must be under {directory}/")


_REQUIRED_ARTIFACTS: Final[tuple[SandboxExpectedArtifact, ...]] = (
    SandboxExpectedArtifact(
        kind="result",
        path=ExpectedArtifactPath("output/result.json"),
        media_type="application/json",
    ),
    SandboxExpectedArtifact(
        kind="summary",
        path=ExpectedArtifactPath("output/summary.md"),
        media_type="text/markdown",
    ),
)


class SandboxOutputSchema(BaseModel):
    """Expected sandbox output with fixed required artifacts and scoped optional ones."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )

    artifacts: Annotated[
        tuple[SandboxExpectedArtifact, ...],
        Field(min_length=len(_REQUIRED_ARTIFACTS), max_length=MAX_OUTPUT_ARTIFACTS),
    ] = _REQUIRED_ARTIFACTS

    @model_validator(mode="after")
    def _validate_artifacts(self) -> SandboxOutputSchema:
        paths = tuple(artifact.path for artifact in self.artifacts)
        if len(set(paths)) != len(paths):
            raise SandboxJobValidationError("artifacts", "must not contain duplicates")
        if not all(artifact in self.artifacts for artifact in _REQUIRED_ARTIFACTS):
            raise SandboxJobValidationError(
                "artifacts", "must include canonical result and summary artifacts"
            )
        return self
