from __future__ import annotations

import errno
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Final, final

import pytest

from vnalpha.sandbox import docker_runner
from vnalpha.sandbox.docker_runner import (
    DockerExecutionRequest,
    DockerExecutionResult,
    parse_docker_image_reference,
)
from vnalpha.sandbox.models import SandboxResourceLimits

_IMAGE: Final = parse_docker_image_reference(
    f"registry.example/openstock/sandbox@sha256:{'a' * 64}"
)


@final
class _FakeDockerCommand:
    """Supply deterministic process outcomes without a Docker daemon."""

    def __init__(
        self,
        outcomes: Iterator[DockerExecutionResult | OSError | subprocess.TimeoutExpired],
    ) -> None:
        self._outcomes = outcomes
        self.calls: list[tuple[str, ...]] = []

    def invoke(
        self, argv: tuple[str, ...], *, timeout_seconds: int
    ) -> DockerExecutionResult:
        del timeout_seconds
        self.calls.append(argv)
        outcome = next(self._outcomes)
        match outcome:
            case DockerExecutionResult():
                return outcome
            case OSError() | subprocess.TimeoutExpired():
                raise outcome
            case unreachable:
                raise AssertionError(f"unexpected fake outcome: {unreachable!r}")


@pytest.mark.parametrize(
    "launch_error",
    (
        PermissionError(errno.EACCES, "permission denied"),
        OSError(errno.EIO, "launch failed"),
    ),
)
def test_run_returns_typed_failure_when_docker_launch_raises_oserror(
    tmp_path: Path,
    launch_error: OSError,
) -> None:
    # Given
    command = _FakeDockerCommand(
        iter(
            (
                DockerExecutionResult(return_code=0, stdout=b"linux\n", stderr=b""),
                DockerExecutionResult(
                    return_code=0, stdout=b"sha256:local", stderr=b""
                ),
                launch_error,
            )
        )
    )
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.run(_request(tmp_path))

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.DOCKER_LAUNCH_FAILED
    assert result.return_code == -1
    assert [argv[1] for argv in command.calls] == ["version", "image", "run"]


def test_run_marks_timeout_cleanup_unsuccessful_when_docker_kill_raises_oserror(
    tmp_path: Path,
) -> None:
    # Given
    command = _FakeDockerCommand(
        iter(
            (
                DockerExecutionResult(return_code=0, stdout=b"linux\n", stderr=b""),
                DockerExecutionResult(
                    return_code=0, stdout=b"sha256:local", stderr=b""
                ),
                subprocess.TimeoutExpired(("docker", "run"), timeout=30),
                OSError(errno.EIO, "cleanup failed"),
            )
        )
    )
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.run(_request(tmp_path))

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.RUNTIME_TIMEOUT
    assert result.cleanup_succeeded is False
    assert command.calls[-1][:2] == ("docker", "kill")


def _request(tmp_path: Path) -> DockerExecutionRequest:
    code_path = tmp_path / "job.py"
    _ = code_path.write_text("print('research')\n")
    output_path = tmp_path / "output"
    output_path.mkdir()
    return DockerExecutionRequest(
        image=_IMAGE,
        code_path=code_path,
        input_paths=(),
        output_path=output_path,
        resource_limits=SandboxResourceLimits(
            cpu_millis=250,
            memory_mb=128,
            timeout_seconds=30,
        ),
    )
