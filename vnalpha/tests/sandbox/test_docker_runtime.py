from __future__ import annotations

import errno
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final, NoReturn, final

import pytest

from vnalpha.sandbox import docker_runner
from vnalpha.sandbox.docker_runner import (
    DockerCommand,
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


def test_preflight_returns_docker_not_found_when_client_is_absent() -> None:
    # Given
    command = _FakeDockerCommand(iter((FileNotFoundError("docker"),)))
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.preflight(_IMAGE)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.DOCKER_NOT_FOUND
    assert [call.argv for call in command.calls] == [_VERSION_ARGV]


@pytest.mark.parametrize(
    "launch_error",
    (
        PermissionError(errno.EACCES, "permission denied"),
        OSError(errno.EIO, "launch failed"),
    ),
)
def test_preflight_returns_structured_failure_when_docker_launch_raises_oserror(
    launch_error: OSError,
) -> None:
    # Given
    command = _FakeDockerCommand(iter((launch_error,)))
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.preflight(_IMAGE)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.DOCKER_LAUNCH_FAILED
    assert result.docker_available is False
    assert [call.argv for call in command.calls] == [_VERSION_ARGV]


def test_preflight_returns_daemon_unavailable_without_image_probe() -> None:
    # Given
    command = _FakeDockerCommand(
        iter((DockerExecutionResult(return_code=1, stdout=b"", stderr=b"down"),))
    )
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.preflight(_IMAGE)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.DAEMON_UNAVAILABLE
    assert [call.argv for call in command.calls] == [_VERSION_ARGV]


def test_preflight_returns_daemon_timeout_without_image_probe() -> None:
    # Given
    command = _FakeDockerCommand(
        iter((subprocess.TimeoutExpired(_VERSION_ARGV, timeout=5),))
    )
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.preflight(_IMAGE)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.DAEMON_TIMEOUT
    assert [call.argv for call in command.calls] == [_VERSION_ARGV]


def test_preflight_rejects_non_linux_docker_server_without_image_probe() -> None:
    # Given
    command = _FakeDockerCommand(
        iter((DockerExecutionResult(return_code=0, stdout=b"windows\n", stderr=b""),))
    )
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.preflight(_IMAGE)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.SERVER_NOT_LINUX
    assert [call.argv for call in command.calls] == [_VERSION_ARGV]


def test_preflight_rejects_absent_local_digest_image_without_pull_or_build() -> None:
    # Given
    image_inspect_argv = (*_IMAGE_INSPECT_PREFIX, str(_IMAGE))
    command = _FakeDockerCommand(
        iter(
            (
                DockerExecutionResult(return_code=0, stdout=b"linux\n", stderr=b""),
                DockerExecutionResult(return_code=1, stdout=b"", stderr=b"missing"),
            )
        )
    )
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.preflight(_IMAGE)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.IMAGE_NOT_AVAILABLE
    assert [call.argv for call in command.calls] == [_VERSION_ARGV, image_inspect_argv]
    assert all(call.argv[1] not in {"build", "pull", "run"} for call in command.calls)


def test_run_does_not_invoke_docker_run_after_failed_preflight(tmp_path: Path) -> None:
    # Given
    request = _request(tmp_path)
    command = _FakeDockerCommand(iter((FileNotFoundError("docker"),)))
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.run(request)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.DOCKER_NOT_FOUND
    assert result.preflight is not None
    assert (
        result.preflight.failure_code
        is docker_runner.DockerFailureCode.DOCKER_NOT_FOUND
    )
    assert [call.argv for call in command.calls] == [_VERSION_ARGV]


def test_run_retains_successful_preflight_with_execution_result(tmp_path: Path) -> None:
    # Given: a Linux daemon, local digest image, and successful container run
    request = _request(tmp_path)
    command = _FakeDockerCommand(
        iter(
            (
                DockerExecutionResult(return_code=0, stdout=b"linux\n", stderr=b""),
                DockerExecutionResult(
                    return_code=0, stdout=b"sha256:local", stderr=b""
                ),
                DockerExecutionResult(return_code=0, stdout=b"result", stderr=b""),
            )
        )
    )

    # When: the hardened runner completes
    result = docker_runner.DockerRunner(command, "Linux").run(request)

    # Then: the exact successful preflight remains attached for persistence
    assert result.preflight is not None
    assert result.preflight.failure_code is None
    assert result.preflight.server_os == "linux"


def test_run_kills_the_deterministic_container_after_a_runtime_timeout(
    tmp_path: Path,
) -> None:
    # Given
    request = _request(tmp_path)
    container_name = docker_runner.docker_container_name(request)
    command = _FakeDockerCommand(
        iter(
            (
                DockerExecutionResult(return_code=0, stdout=b"linux\n", stderr=b""),
                DockerExecutionResult(
                    return_code=0, stdout=b"sha256:local", stderr=b""
                ),
                subprocess.TimeoutExpired(("docker", "run"), timeout=30),
                DockerExecutionResult(return_code=0, stdout=b"", stderr=b""),
            )
        )
    )
    runner = docker_runner.DockerRunner(command=command, host_platform="Linux")

    # When
    result = runner.run(request)

    # Then
    assert result.failure_code is docker_runner.DockerFailureCode.RUNTIME_TIMEOUT
    assert command.calls[-1].argv == ("docker", "kill", str(container_name))
    assert command.calls[-1].timeout_seconds == 5


def test_subprocess_adapter_uses_minimal_shell_free_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    observed: dict[str, tuple[str, ...] | bool | int | Mapping[str, str]] = {}

    class _SmallOutputProcess:
        stdout = BytesIO(b"out")
        stderr = BytesIO(b"err")

        def wait(self, timeout: int) -> int:
            assert timeout == 5
            return 0

    def fake_popen(
        argv: tuple[str, ...],
        **kwargs: tuple[str, ...] | bool | int | Mapping[str, str],
    ) -> _SmallOutputProcess:
        observed["argv"] = argv
        observed.update(kwargs)

        return _SmallOutputProcess()

    def reject_unbounded_run(
        *args: str | tuple[str, ...],
        **kwargs: bool | int | Mapping[str, str],
    ) -> NoReturn:
        del args, kwargs
        raise AssertionError("subprocess.run must not capture Docker output")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subprocess, "run", reject_unbounded_run)
    command: DockerCommand = docker_runner.SubprocessDockerCommand()

    # When
    result = command.invoke(_VERSION_ARGV, timeout_seconds=5)

    # Then
    assert observed["argv"] == _VERSION_ARGV
    assert observed["shell"] is False
    assert observed["close_fds"] is True
    environment = observed["env"]
    assert isinstance(environment, Mapping)
    assert set(environment) == {"LANG", "LC_ALL", "PATH"}
    assert result.stdout == b"out"
    assert result.stderr == b"err"


def test_subprocess_adapter_bounds_output_while_reading_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    class _BoundedReadStream(BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            assert size is not None
            assert 0 < size <= docker_runner.MAX_DOCKER_CAPTURE_BYTES
            return super().read(size)

    class _LargeOutputProcess:
        stdout = _BoundedReadStream(b"o" * (docker_runner.MAX_DOCKER_CAPTURE_BYTES + 1))
        stderr = _BoundedReadStream(b"e" * (docker_runner.MAX_DOCKER_CAPTURE_BYTES + 1))

        def wait(self, timeout: int) -> int:
            assert timeout == 5
            return 0

    def fake_popen(
        argv: tuple[str, ...],
        **kwargs: bool | int | Mapping[str, str],
    ) -> _LargeOutputProcess:
        del argv, kwargs
        return _LargeOutputProcess()

    def reject_unbounded_run(
        *args: str | tuple[str, ...],
        **kwargs: bool | int | Mapping[str, str],
    ) -> NoReturn:
        del args, kwargs
        raise AssertionError("subprocess.run must not capture Docker output")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subprocess, "run", reject_unbounded_run)
    command: DockerCommand = docker_runner.SubprocessDockerCommand()

    # When
    result = command.invoke(_VERSION_ARGV, timeout_seconds=5)

    # Then
    assert len(result.stdout) == docker_runner.MAX_DOCKER_CAPTURE_BYTES
    assert len(result.stderr) == docker_runner.MAX_DOCKER_CAPTURE_BYTES
    assert result.stdout_truncated
    assert result.stderr_truncated


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
