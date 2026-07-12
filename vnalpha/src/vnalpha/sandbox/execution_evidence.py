"""Immutable canonical execution evidence for bounded sandbox runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict, final

from vnalpha.sandbox.docker_runtime import DockerExecutionResult, DockerFailureCode

_SCHEMA_VERSION = 1


class SandboxExecutionStatus(StrEnum):
    """Terminal execution classifications stored as durable evidence."""

    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


class SandboxExecutionFailureCode(StrEnum):
    """Evidence-only failures detected after a runner returns malformed data."""

    INVALID_RUNNER_RESULT = "invalid_runner_result"


class _ExecutionPayload(TypedDict):
    cleanup_succeeded: bool | None
    detail: str
    failure_code: str | None
    return_code: int
    schema_version: int
    status: str
    stderr_truncated: bool
    stdout_truncated: bool


@final
@dataclass(frozen=True, slots=True)
class SandboxExecutionEvidence:
    """Redacted metadata and exact bounded streams for one Docker run."""

    status: SandboxExecutionStatus
    return_code: int
    stdout: bytes
    stderr: bytes
    failure_code: DockerFailureCode | SandboxExecutionFailureCode | None
    detail: str
    stdout_truncated: bool
    stderr_truncated: bool
    cleanup_succeeded: bool | None

    @classmethod
    def from_result(
        cls,
        status: SandboxExecutionStatus,
        result: DockerExecutionResult,
        failure_code: DockerFailureCode | SandboxExecutionFailureCode | None = None,
    ) -> SandboxExecutionEvidence:
        """Bind a runner result to its controller-determined terminal status."""

        return cls(
            status=status,
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            failure_code=(
                result.failure_code if failure_code is None else failure_code
            ),
            detail=result.detail,
            stdout_truncated=result.stdout_truncated,
            stderr_truncated=result.stderr_truncated,
            cleanup_succeeded=result.cleanup_succeeded,
        )

    def to_json_bytes(self) -> bytes:
        """Serialize stable redacted metadata without duplicating captured streams."""

        payload: _ExecutionPayload = {
            "cleanup_succeeded": self.cleanup_succeeded,
            "detail": self.detail,
            "failure_code": (
                None if self.failure_code is None else self.failure_code.value
            ),
            "return_code": self.return_code,
            "schema_version": _SCHEMA_VERSION,
            "status": self.status.value,
            "stderr_truncated": self.stderr_truncated,
            "stdout_truncated": self.stdout_truncated,
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
