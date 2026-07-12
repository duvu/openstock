"""Bounded shell-free subprocess adapter for Docker commands."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import MappingProxyType
from typing import IO, Final, final

from vnalpha.sandbox.docker_runtime import DockerExecutionResult

MAX_DOCKER_CAPTURE_BYTES: Final = 64 * 1024
_CAPTURE_READ_BYTES: Final = 8 * 1024
_MINIMAL_DOCKER_ENV: Final[Mapping[str, str]] = MappingProxyType(
    {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    }
)


@final
@dataclass(frozen=True, slots=True)
class _CapturedOutput:
    data: bytes
    truncated: bool


@final
class SubprocessDockerCommand:
    """Execute Docker with bounded streaming capture and no inherited environment."""

    def invoke(
        self, argv: tuple[str, ...], *, timeout_seconds: int
    ) -> DockerExecutionResult:
        process = subprocess.Popen(
            argv,
            close_fds=True,
            env=_MINIMAL_DOCKER_ENV,
            shell=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        assert process.stdout is not None
        assert process.stderr is not None
        with ThreadPoolExecutor(max_workers=2) as executor:
            stdout_future = executor.submit(_capture_stream, process.stdout)
            stderr_future = executor.submit(_capture_stream, process.stderr)
            try:
                return_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                _ = process.wait()
                raise
        stdout = stdout_future.result()
        stderr = stderr_future.result()
        return DockerExecutionResult(
            return_code=return_code,
            stdout=stdout.data,
            stderr=stderr.data,
            stdout_truncated=stdout.truncated,
            stderr_truncated=stderr.truncated,
        )


def _capture_stream(stream: IO[bytes]) -> _CapturedOutput:
    captured = bytearray()
    truncated = False
    while chunk := stream.read(_CAPTURE_READ_BYTES):
        remaining = MAX_DOCKER_CAPTURE_BYTES - len(captured)
        captured.extend(chunk[:remaining])
        truncated = truncated or len(chunk) > remaining
    return _CapturedOutput(data=bytes(captured), truncated=truncated)
