from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, final

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
_VERSION_ARGV: Final = ("docker", "version", "--format", "{{.Server.Os}}")
_IMAGE_INSPECT_PREFIX: Final = ("docker", "image", "inspect", "--format", "{{.Id}}")


@final
@dataclass(frozen=True, slots=True)
class _Invocation:
    argv: tuple[str, ...]
    timeout_seconds: int


@final
class _FakeDockerCommand:
    """A stateful process fake that supplies one outcome per fixed invocation."""

    def __init__(
        self,
        outcomes: Iterator[DockerExecutionResult | OSError | subprocess.TimeoutExpired],
    ) -> None:
        self._outcomes = outcomes
        self.calls: list[_Invocation] = []

    def invoke(
        self, argv: tuple[str, ...], *, timeout_seconds: int
    ) -> DockerExecutionResult:
        self.calls.append(_Invocation(argv=argv, timeout_seconds=timeout_seconds))
        outcome = next(self._outcomes)
        match outcome:
            case DockerExecutionResult():
                return outcome
            case OSError() | subprocess.TimeoutExpired():
                raise outcome
            case unreachable:
                raise AssertionError(f"unexpected fake outcome: {unreachable!r}")


def test_preflight_rejects_non_linux_before_invoking_docker() -> None:
    # Given
    command = _FakeDockerCommand(iter(()))
    runner = docker_runner.DockerRunner(command=command, host_platform="Darwin")

    # When
    result = runner.preflight(_IMAGE)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.HOST_NOT_LINUX
    assert command.calls == []


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
