"""Fail-closed Docker preflight and subprocess execution adapter."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final, Protocol, final

from vnalpha.sandbox.docker_policy import (
    DockerContainerName,
    DockerExecutionRequest,
    DockerImageReference,
    build_docker_run_argv,
    docker_container_name,
)

_CLEANUP_TIMEOUT_SECONDS: Final = 5
_FAILED_RETURN_CODE: Final = -1
_PREFLIGHT_TIMEOUT_SECONDS: Final = 5
_VERSION_ARGV: Final = ("docker", "version", "--format", "{{.Server.Os}}")


@final
@dataclass(frozen=True, slots=True)
class _PreflightState:
    docker_available: bool
    linux_supported: bool
    server_os: str | None = None


_DOCKER_UNAVAILABLE: Final = _PreflightState(False, True)
_DAEMON_AVAILABLE: Final = _PreflightState(True, True)


class DockerFailureCode(StrEnum):
    """Safe machine-readable Docker execution outcomes."""

    HOST_NOT_LINUX = "host_not_linux"
    DOCKER_LAUNCH_FAILED = "docker_launch_failed"
    DOCKER_NOT_FOUND = "docker_not_found"
    DAEMON_UNAVAILABLE = "daemon_unavailable"
    DAEMON_TIMEOUT = "daemon_timeout"
    SERVER_NOT_LINUX = "server_not_linux"
    IMAGE_NOT_AVAILABLE = "image_not_available"
    IMAGE_PROBE_TIMEOUT = "image_probe_timeout"
    RUNTIME_TIMEOUT = "runtime_timeout"
    RUNTIME_FAILED = "runtime_failed"


@final
@dataclass(frozen=True, slots=True)
class DockerPreflightResult:
    """The structured outcome of checks required before Docker execution."""

    docker_available: bool
    linux_supported: bool
    detail: str
    failure_code: DockerFailureCode | None = None
    server_os: str | None = None


@final
@dataclass(frozen=True, slots=True)
class DockerExecutionResult:
    """The bounded result from one Docker command invocation."""

    return_code: int
    stdout: bytes
    stderr: bytes
    failure_code: DockerFailureCode | None = None
    detail: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    cleanup_succeeded: bool | None = None
    preflight: DockerPreflightResult | None = None


class DockerCommand(Protocol):
    """A fakeable boundary for one already-validated Docker argv tuple."""

    def invoke(
        self, argv: tuple[str, ...], *, timeout_seconds: int
    ) -> DockerExecutionResult:
        """Execute Docker without a shell using the supplied bounded timeout."""

        ...


@final
@dataclass(frozen=True, slots=True)
class DockerRunner:
    """Run only a verified local Linux Docker image through a fixed command boundary."""

    command: DockerCommand
    host_platform: str

    def preflight(self, image: DockerImageReference) -> DockerPreflightResult:
        """Check host, daemon, Linux server, and the exact local digest image."""

        if self.host_platform != "Linux":
            return DockerPreflightResult(
                docker_available=False,
                linux_supported=False,
                detail="Docker sandbox execution requires a Linux host",
                failure_code=DockerFailureCode.HOST_NOT_LINUX,
            )
        try:
            server_probe = self.command.invoke(
                _VERSION_ARGV, timeout_seconds=_PREFLIGHT_TIMEOUT_SECONDS
            )
        except FileNotFoundError:
            return _preflight_failure(
                DockerFailureCode.DOCKER_NOT_FOUND,
                "Docker client is not available",
                _DOCKER_UNAVAILABLE,
            )
        except OSError:
            return _preflight_failure(
                DockerFailureCode.DOCKER_LAUNCH_FAILED,
                "Docker command could not be launched",
                _DOCKER_UNAVAILABLE,
            )
        except subprocess.TimeoutExpired:
            return _preflight_failure(
                DockerFailureCode.DAEMON_TIMEOUT,
                "Docker daemon preflight timed out",
                _DAEMON_AVAILABLE,
            )
        if server_probe.return_code != 0:
            return _preflight_failure(
                DockerFailureCode.DAEMON_UNAVAILABLE,
                "Docker daemon preflight failed",
                _DAEMON_AVAILABLE,
            )
        server_os = (
            server_probe.stdout.decode("ascii", errors="replace").strip().lower()
        )
        if server_os != "linux":
            return _preflight_failure(
                DockerFailureCode.SERVER_NOT_LINUX,
                "Docker server must run Linux containers",
                _PreflightState(True, False, server_os),
            )
        linux_server = _PreflightState(True, True, server_os)
        try:
            image_probe = self.command.invoke(
                ("docker", "image", "inspect", "--format", "{{.Id}}", str(image)),
                timeout_seconds=_PREFLIGHT_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            return _preflight_failure(
                DockerFailureCode.DOCKER_NOT_FOUND,
                "Docker client is not available",
                _PreflightState(False, True, server_os),
            )
        except OSError:
            return _preflight_failure(
                DockerFailureCode.DOCKER_LAUNCH_FAILED,
                "Docker command could not be launched",
                _PreflightState(False, True, server_os),
            )
        except subprocess.TimeoutExpired:
            return _preflight_failure(
                DockerFailureCode.IMAGE_PROBE_TIMEOUT,
                "Local Docker image probe timed out",
                linux_server,
            )
        if image_probe.return_code != 0:
            return _preflight_failure(
                DockerFailureCode.IMAGE_NOT_AVAILABLE,
                "Required local digest image is unavailable",
                linux_server,
            )
        return DockerPreflightResult(
            docker_available=True,
            linux_supported=True,
            detail="Docker daemon and required local digest image are available",
            server_os=server_os,
        )

    def run(self, request: DockerExecutionRequest) -> DockerExecutionResult:
        """Run one validated request only after its fail-closed preflight succeeds."""

        preflight = self.preflight(request.image)
        if preflight.failure_code is not None:
            return _failed_execution(
                preflight.failure_code, preflight.detail, preflight=preflight
            )
        container_name = docker_container_name(request)
        try:
            execution = self.command.invoke(
                build_docker_run_argv(request),
                timeout_seconds=request.resource_limits.timeout_seconds,
            )
        except FileNotFoundError:
            return _failed_execution(
                DockerFailureCode.DOCKER_NOT_FOUND,
                "Docker client is not available",
                preflight=preflight,
            )
        except OSError:
            return _failed_execution(
                DockerFailureCode.DOCKER_LAUNCH_FAILED,
                "Docker command could not be launched",
                preflight=preflight,
            )
        except subprocess.TimeoutExpired:
            return DockerExecutionResult(
                return_code=_FAILED_RETURN_CODE,
                stdout=b"",
                stderr=b"",
                failure_code=DockerFailureCode.RUNTIME_TIMEOUT,
                detail="Docker execution timed out",
                cleanup_succeeded=self._kill_container(container_name),
                preflight=preflight,
            )
        if execution.return_code == 0:
            return replace(execution, preflight=preflight)
        return DockerExecutionResult(
            return_code=execution.return_code,
            stdout=execution.stdout,
            stderr=execution.stderr,
            failure_code=DockerFailureCode.RUNTIME_FAILED,
            detail="Docker execution failed",
            stdout_truncated=execution.stdout_truncated,
            stderr_truncated=execution.stderr_truncated,
            preflight=preflight,
        )

    def _kill_container(self, container_name: DockerContainerName) -> bool:
        try:
            cleanup = self.command.invoke(
                ("docker", "kill", str(container_name)),
                timeout_seconds=_CLEANUP_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return cleanup.return_code == 0


def _preflight_failure(
    failure_code: DockerFailureCode,
    detail: str,
    state: _PreflightState,
) -> DockerPreflightResult:
    return DockerPreflightResult(
        docker_available=state.docker_available,
        linux_supported=state.linux_supported,
        detail=detail,
        failure_code=failure_code,
        server_os=state.server_os,
    )


def _failed_execution(
    failure_code: DockerFailureCode,
    detail: str,
    *,
    preflight: DockerPreflightResult | None = None,
) -> DockerExecutionResult:
    return DockerExecutionResult(
        return_code=_FAILED_RETURN_CODE,
        stdout=b"",
        stderr=b"",
        failure_code=failure_code,
        detail=detail,
        preflight=preflight,
    )
