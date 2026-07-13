from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vnalpha.observability.context import (
    RunContext,
    get_correlation_id,
    get_run_context,
    init_run_context,
    set_correlation_id,
)
from vnalpha.sandbox.docker_policy import (
    DockerExecutionRequest,
    DockerImageReference,
)
from vnalpha.sandbox.docker_runner import (
    DockerExecutionResult,
    DockerRunner,
    SubprocessDockerCommand,
)
from vnalpha.sandbox.models import SandboxCorrelationId, SandboxRunId


class SandboxDockerRunner(Protocol):
    def run(self, request: DockerExecutionRequest) -> DockerExecutionResult: ...


@dataclass(frozen=True, slots=True)
class SandboxRuntimeConfiguration:
    surface: str
    run_context: RunContext | None
    image: DockerImageReference
    docker_runner: SandboxDockerRunner | None


class SandboxRuntimeContext:
    __slots__ = ("_configuration", "_run_context")

    def __init__(self, configuration: SandboxRuntimeConfiguration) -> None:
        self._configuration = configuration
        self._run_context = configuration.run_context

    @property
    def image(self) -> DockerImageReference:
        return self._configuration.image

    def runner(self) -> SandboxDockerRunner:
        if self._configuration.docker_runner is not None:
            return self._configuration.docker_runner
        return DockerRunner(SubprocessDockerCommand(), platform.system())

    def resolve_run_context(self) -> RunContext:
        if self._run_context is not None:
            return self._run_context
        current = get_run_context()
        if current is not None:
            self._run_context = current
            return current
        self._run_context = init_run_context(
            surface=self._configuration.surface,
            actor=self._configuration.surface,
            log_root=Path(os.environ.get("VNALPHA_LOG_ROOT", "/tmp/openstock-logs")),
        )
        return self._run_context

    def for_run(self, run_id: SandboxRunId) -> RunContext:
        current = self.resolve_run_context()
        if current.run_id == str(run_id):
            return current
        return RunContext(
            run_id=str(run_id),
            surface=current.surface,
            actor=current.actor,
            log_root=current.log_root,
        )

    def ensure_correlation_id(self) -> SandboxCorrelationId:
        correlation_id = get_correlation_id()
        if correlation_id in {"", "unset"}:
            correlation_id = set_correlation_id()
        return SandboxCorrelationId(correlation_id)
