"""Strict, descriptor-safe validation of canonical sandbox outputs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, final

from vnalpha.sandbox._output_validation_types import (
    SandboxOutputValidationEvidence,
    SandboxOutputValidationFailureCode,
    SandboxOutputValidationResult,
    SandboxOutputValidationStatus,
    SandboxResultArtifactReference,
    SandboxResultEnvelope,
    parse_result,
)
from vnalpha.sandbox.artifact_manifest import SandboxArtifactManifestEntry
from vnalpha.sandbox.contracts import SandboxExpectedArtifact, SandboxOutputSchema
from vnalpha.sandbox.storage import (
    SandboxArtifactNotFoundError,
    SandboxArtifactPathError,
    SandboxArtifactSizeError,
    SandboxArtifactStorage,
    SandboxArtifactTypeError,
)

__all__ = (
    "SandboxOutputValidationEvidence",
    "SandboxOutputValidationFailureCode",
    "SandboxOutputValidationResult",
    "SandboxOutputValidationStatus",
    "SandboxOutputValidator",
    "SandboxResultArtifactReference",
    "SandboxResultEnvelope",
)

MAX_RESULT_JSON_BYTES: Final = 1_048_576
MAX_SUMMARY_MARKDOWN_BYTES: Final = 262_144
MAX_OPTIONAL_ARTIFACT_BYTES: Final = 10_485_760
_RESULT_PATH: Final = "output/result.json"
_SUMMARY_PATH: Final = "output/summary.md"


@final
class SandboxOutputValidator:
    """Validate only canonical schema-declared output files through safe storage."""

    def __init__(self, storage: SandboxArtifactStorage) -> None:
        self._storage = storage

    def validate(
        self, output_schema: SandboxOutputSchema
    ) -> SandboxOutputValidationResult:
        """Read required outputs first, then only declared optional artifacts in order."""

        result_read = self._read(
            _RESULT_PATH, MAX_RESULT_JSON_BYTES, "application/json"
        )
        match result_read:
            case _ReadFailure(code=code):
                return self._failed(code, _RESULT_PATH, ())
            case _ReadSuccess(entry=result_entry, content=content):
                parsed_result = parse_result(content)
                if parsed_result is None:
                    return self._failed(
                        SandboxOutputValidationFailureCode.INVALID_RESULT,
                        _RESULT_PATH,
                        (result_entry,),
                    )

        summary_read = self._read(
            _SUMMARY_PATH, MAX_SUMMARY_MARKDOWN_BYTES, "text/markdown"
        )
        match summary_read:
            case _ReadFailure(code=code):
                return self._failed(code, _SUMMARY_PATH, (result_entry,))
            case _ReadSuccess(entry=summary_entry, content=content):
                if not _is_nonblank_utf8(content):
                    return self._failed(
                        SandboxOutputValidationFailureCode.INVALID_SUMMARY,
                        _SUMMARY_PATH,
                        (result_entry, summary_entry),
                    )

        inventory = (result_entry, summary_entry)
        for artifact in _optional_artifacts(output_schema):
            observed = self._read(
                str(artifact.path), MAX_OPTIONAL_ARTIFACT_BYTES, artifact.media_type
            )
            match observed:
                case _ReadFailure(code=code):
                    return self._failed(code, str(artifact.path), inventory)
                case _ReadSuccess(entry=entry):
                    inventory += (entry,)

        if not _references_match(parsed_result, output_schema):
            return self._failed(
                SandboxOutputValidationFailureCode.ARTIFACT_REFERENCE_MISMATCH,
                _RESULT_PATH,
                inventory,
            )
        return SandboxOutputValidationResult(
            evidence=SandboxOutputValidationEvidence(
                status=SandboxOutputValidationStatus.SUCCEEDED,
                failure_code=None,
                artifact_path=None,
                detail="sandbox outputs satisfy the expected artifact contract",
                validated_paths=tuple(entry.path for entry in inventory),
            ),
            result=parsed_result,
            inventory=inventory,
        )

    def _read(self, path: str, max_bytes: int, media_type: str) -> _ReadResult:
        try:
            content = self._storage.read_bounded_regular_file(path, max_bytes=max_bytes)
        except SandboxArtifactNotFoundError:
            return _ReadFailure(SandboxOutputValidationFailureCode.MISSING_ARTIFACT)
        except SandboxArtifactSizeError:
            return _ReadFailure(SandboxOutputValidationFailureCode.ARTIFACT_TOO_LARGE)
        except (SandboxArtifactPathError, SandboxArtifactTypeError):
            return _ReadFailure(SandboxOutputValidationFailureCode.UNSAFE_ARTIFACT)
        return _ReadSuccess(
            content=content,
            entry=SandboxArtifactManifestEntry(
                path=path,
                sha256=hashlib.sha256(content).hexdigest(),
                byte_length=len(content),
                media_type=media_type,
            ),
        )

    def _failed(
        self,
        code: SandboxOutputValidationFailureCode,
        path: str,
        inventory: tuple[SandboxArtifactManifestEntry, ...],
    ) -> SandboxOutputValidationResult:
        return SandboxOutputValidationResult(
            evidence=SandboxOutputValidationEvidence(
                status=SandboxOutputValidationStatus.FAILED,
                failure_code=code,
                artifact_path=path,
                detail=_failure_detail(code),
                validated_paths=tuple(entry.path for entry in inventory),
            ),
            result=None,
            inventory=inventory,
        )


@final
@dataclass(frozen=True, slots=True)
class _ReadSuccess:
    content: bytes
    entry: SandboxArtifactManifestEntry


@final
@dataclass(frozen=True, slots=True)
class _ReadFailure:
    code: SandboxOutputValidationFailureCode


_ReadResult = _ReadSuccess | _ReadFailure


def _is_nonblank_utf8(content: bytes) -> bool:
    try:
        return bool(content.decode("utf-8").strip())
    except UnicodeDecodeError:
        return False


def _optional_artifacts(
    output_schema: SandboxOutputSchema,
) -> tuple[SandboxExpectedArtifact, ...]:
    artifacts: tuple[SandboxExpectedArtifact, ...] = ()
    for artifact in output_schema.artifacts:
        match artifact.kind:
            case "result" | "summary":
                continue
            case "chart" | "table":
                artifacts += (artifact,)
    return artifacts


def _references_match(
    result: SandboxResultEnvelope, output_schema: SandboxOutputSchema
) -> bool:
    expected = frozenset(
        (artifact.kind, artifact.path)
        for artifact in _optional_artifacts(output_schema)
    )
    observed = frozenset(
        (reference.kind, reference.path) for reference in result.artifacts
    )
    return observed == expected


def _failure_detail(code: SandboxOutputValidationFailureCode) -> str:
    match code:
        case SandboxOutputValidationFailureCode.MISSING_ARTIFACT:
            return "expected sandbox artifact is missing"
        case SandboxOutputValidationFailureCode.UNSAFE_ARTIFACT:
            return "expected sandbox artifact is unsafe"
        case SandboxOutputValidationFailureCode.ARTIFACT_TOO_LARGE:
            return "expected sandbox artifact exceeds the byte limit"
        case SandboxOutputValidationFailureCode.INVALID_RESULT:
            return "sandbox result does not satisfy the output contract"
        case SandboxOutputValidationFailureCode.INVALID_SUMMARY:
            return "sandbox summary does not satisfy the output contract"
        case SandboxOutputValidationFailureCode.ARTIFACT_REFERENCE_MISMATCH:
            return "sandbox artifact references do not match the expected contract"
