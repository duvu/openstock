"""Immutable canonical execution evidence for bounded sandbox runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict, final

from vnalpha.sandbox.docker_policy import (
    DockerExecutionRequest,
    DockerSecurityProfile,
    effective_security_profile,
)
from vnalpha.sandbox.docker_runtime import (
    DockerExecutionResult,
    DockerFailureCode,
    DockerPreflightResult,
)

_SCHEMA_VERSION = 2


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
    preflight: _PreflightPayload | None
    security_controls: _SecurityControlsPayload | None
    status: str
    stderr_truncated: bool
    stdout_truncated: bool


class _PreflightPayload(TypedDict):
    detail: str
    docker_available: bool
    failure_code: str | None
    linux_supported: bool
    server_os: str | None


class _SecurityControlsPayload(TypedDict):
    capabilities_dropped: str
    code_read_only: bool
    cpu_millis: int
    environment_forwarded: bool
    image_digest: str
    input_mount_count: int
    inputs_read_only: bool
    memory_mb: int
    network: str
    no_new_privileges: bool
    output_read_write: bool
    pids_limit: int
    pull_policy: str
    root_read_only: bool
    timeout_seconds: int
    user_id: int


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
    preflight: DockerPreflightResult | None
    security_controls: DockerSecurityProfile | None

    @classmethod
    def from_result(
        cls,
        status: SandboxExecutionStatus,
        result: DockerExecutionResult,
        request: DockerExecutionRequest | None = None,
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
            preflight=result.preflight,
            security_controls=(
                None if request is None else effective_security_profile(request)
            ),
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
            "preflight": _preflight_payload(self.preflight),
            "security_controls": _security_controls_payload(self.security_controls),
            "status": self.status.value,
            "stderr_truncated": self.stderr_truncated,
            "stdout_truncated": self.stdout_truncated,
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")


def _preflight_payload(
    preflight: DockerPreflightResult | None,
) -> _PreflightPayload | None:
    if preflight is None:
        return None
    return {
        "detail": preflight.detail,
        "docker_available": preflight.docker_available,
        "failure_code": (
            None if preflight.failure_code is None else preflight.failure_code.value
        ),
        "linux_supported": preflight.linux_supported,
        "server_os": preflight.server_os,
    }


def _security_controls_payload(
    profile: DockerSecurityProfile | None,
) -> _SecurityControlsPayload | None:
    if profile is None:
        return None
    return {
        "capabilities_dropped": profile.capabilities_dropped,
        "code_read_only": profile.code_read_only,
        "cpu_millis": profile.cpu_millis,
        "environment_forwarded": profile.environment_forwarded,
        "image_digest": profile.image_digest,
        "input_mount_count": profile.input_mount_count,
        "inputs_read_only": profile.inputs_read_only,
        "memory_mb": profile.memory_mb,
        "network": profile.network,
        "no_new_privileges": profile.no_new_privileges,
        "output_read_write": profile.output_read_write,
        "pids_limit": profile.pids_limit,
        "pull_policy": profile.pull_policy,
        "root_read_only": profile.root_read_only,
        "timeout_seconds": profile.timeout_seconds,
        "user_id": profile.user_id,
    }
