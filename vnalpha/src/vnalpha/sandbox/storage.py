"""Run-scoped artifact path containment for sandbox jobs."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import TracebackType
from typing import Self, final, override

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.models import SandboxJobId


@final
@dataclass(frozen=True, slots=True)
class SandboxArtifactPathError(ValueError):
    """An artifact path is not contained in the job's canonical directory."""

    path: str

    @override
    def __str__(self) -> str:
        return f"sandbox artifact path is unsafe: {self.path}"


@final
class SandboxArtifactStorage:
    """Create and resolve artifact paths exclusively below one sandbox job directory."""

    def __init__(self, run_context: RunContext, job_id: SandboxJobId) -> None:
        if sys.platform != "linux":
            raise SandboxArtifactPathError(str(run_context.run_dir))
        job_component = _parse_job_component(job_id)
        run_fd = _open_directory(run_context.run_dir, str(run_context.run_dir))
        sandbox_fd: int | None = None
        job_fd: int | None = None
        try:
            sandbox_fd = _open_or_create_directory(run_fd, "sandbox", "sandbox")
            job_fd = _open_or_create_directory(sandbox_fd, job_component, job_component)
            self._job_fd: int = job_fd
            job_fd = None
            self.job_dir: Path = run_context.run_dir / "sandbox" / job_component
        finally:
            _close_fd(job_fd)
            _close_fd(sandbox_fd)
            _close_fd(run_fd)

    def path_for(self, raw_path: str) -> Path:
        """Return an informational contained path; use write_bytes for secure writes."""

        path = PurePosixPath(raw_path)
        windows_path = PureWindowsPath(raw_path)
        is_relative = (
            bool(path.parts)
            and not path.is_absolute()
            and not windows_path.is_absolute()
            and ".." not in path.parts
            and ".." not in windows_path.parts
        )
        if not is_relative:
            raise SandboxArtifactPathError(raw_path)
        artifact_path = self.job_dir / path
        if not artifact_path.resolve().is_relative_to(self.job_dir.resolve()):
            raise SandboxArtifactPathError(raw_path)
        return artifact_path

    def write_bytes(self, raw_path: str, content: bytes) -> Path:
        """Write bytes through Linux directory descriptors without following symlinks."""

        parts = _parse_artifact_parts(raw_path)
        root_fd = _duplicate_job_fd(self._job_fd, raw_path)
        current_fd = root_fd
        try:
            for component in parts[:-1]:
                next_fd = _open_or_create_directory(current_fd, component, raw_path)
                os.close(current_fd)
                current_fd = next_fd
            artifact_fd = _open_artifact(current_fd, parts[-1], raw_path)
            try:
                written = 0
                while written < len(content):
                    written += os.write(artifact_fd, content[written:])
            finally:
                os.close(artifact_fd)
        finally:
            os.close(current_fd)
        return self.job_dir.joinpath(*parts)

    def close(self) -> None:
        """Release the anchored job-directory descriptor."""

        job_fd = self._job_fd
        self._job_fd = -1
        _close_fd(job_fd)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _parse_job_component(job_id: SandboxJobId) -> str:
    value = str(job_id)
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    is_safe_component = (
        bool(value)
        and len(posix_path.parts) == 1
        and len(windows_path.parts) == 1
        and not posix_path.is_absolute()
        and not windows_path.is_absolute()
        and value not in {".", ".."}
    )
    if not is_safe_component:
        raise SandboxArtifactPathError(value)
    return value


def _parse_artifact_parts(raw_path: str) -> tuple[str, ...]:
    path = PurePosixPath(raw_path)
    windows_path = PureWindowsPath(raw_path)
    is_safe = (
        bool(path.parts)
        and not path.is_absolute()
        and not windows_path.is_absolute()
        and ".." not in path.parts
        and ".." not in windows_path.parts
    )
    if not is_safe:
        raise SandboxArtifactPathError(raw_path)
    return path.parts


def _open_directory(path: Path, raw_path: str) -> int:
    try:
        return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise SandboxArtifactPathError(raw_path) from exc


def _open_or_create_directory(parent_fd: int, component: str, raw_path: str) -> int:
    try:
        os.mkdir(component, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        _ = os.lstat(component, dir_fd=parent_fd)
    try:
        child_fd = os.open(
            component,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise SandboxArtifactPathError(raw_path) from exc
    return child_fd


def _duplicate_job_fd(job_fd: int, raw_path: str) -> int:
    if job_fd < 0:
        raise SandboxArtifactPathError(raw_path)
    try:
        return os.dup(job_fd)
    except OSError as exc:
        raise SandboxArtifactPathError(raw_path) from exc


def _close_fd(fd: int | None) -> None:
    if fd is not None and fd >= 0:
        os.close(fd)


def _open_artifact(parent_fd: int, name: str, raw_path: str) -> int:
    try:
        return os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
            mode=0o600,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise SandboxArtifactPathError(raw_path) from exc
