"""Run-scoped artifact path containment for sandbox jobs."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import TracebackType
from typing import Self, final

from vnalpha.observability.context import RunContext
from vnalpha.sandbox import _descriptor
from vnalpha.sandbox._atomic import write_atomic_file
from vnalpha.sandbox._descriptor import (
    SandboxArtifactNotFoundError,
    SandboxArtifactPathError,
    SandboxArtifactSizeError,
    SandboxArtifactTypeError,
)
from vnalpha.sandbox.models import SandboxJobId

__all__ = (
    "SandboxArtifactNotFoundError",
    "SandboxArtifactPathError",
    "SandboxArtifactSizeError",
    "SandboxArtifactStorage",
    "SandboxArtifactTypeError",
)


@final
class SandboxArtifactStorage:
    """Create and resolve artifact paths exclusively below one sandbox job directory."""

    def __init__(self, run_context: RunContext, job_id: SandboxJobId) -> None:
        if sys.platform != "linux":
            raise SandboxArtifactPathError(str(run_context.run_dir))
        job_component = _parse_job_component(job_id)
        run_fd = _descriptor.open_directory(
            run_context.run_dir, str(run_context.run_dir)
        )
        sandbox_fd: int | None = None
        job_fd: int | None = None
        try:
            sandbox_fd = _descriptor.open_or_create_directory(
                run_fd, "sandbox", "sandbox"
            )
            job_fd = _descriptor.open_or_create_directory(
                sandbox_fd, job_component, job_component
            )
            self._job_fd: int = job_fd
            self._run_context = run_context
            job_fd = None
            self.job_dir: Path = run_context.run_dir / "sandbox" / job_component
        finally:
            _descriptor.close_fd(job_fd)
            _descriptor.close_fd(sandbox_fd)
            _descriptor.close_fd(run_fd)

    @property
    def run_context(self) -> RunContext:
        """Return the trusted run context used to anchor this storage instance."""

        return self._run_context

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
        """Write bytes atomically through the compatibility storage API."""

        return self.write_atomic_bytes(raw_path, content)

    def ensure_directory(self, raw_path: str) -> Path:
        """Create and return a directory contained below this job descriptor."""

        parts = _descriptor.parse_artifact_parts(raw_path)
        current_fd = _descriptor.duplicate_job_fd(self._job_fd, raw_path)
        try:
            for component in parts:
                next_fd = _descriptor.open_or_create_directory(
                    current_fd, component, raw_path
                )
                os.close(current_fd)
                current_fd = next_fd
        finally:
            os.close(current_fd)
        return self.job_dir.joinpath(*parts)

    def write_atomic_bytes(self, raw_path: str, content: bytes) -> Path:
        """Atomically replace bytes through Linux descriptors without following symlinks."""

        parts = _descriptor.parse_artifact_parts(raw_path)
        root_fd = _descriptor.duplicate_job_fd(self._job_fd, raw_path)
        current_fd = root_fd
        try:
            for component in parts[:-1]:
                next_fd = _descriptor.open_or_create_directory(
                    current_fd, component, raw_path
                )
                os.close(current_fd)
                current_fd = next_fd
            try:
                write_atomic_file(current_fd, parts[-1], content)
            except OSError as exc:
                raise SandboxArtifactPathError(raw_path) from exc
        finally:
            os.close(current_fd)
        return self.job_dir.joinpath(*parts)

    def read_bounded_regular_file(self, raw_path: str, *, max_bytes: int) -> bytes:
        """Read a bounded contained regular file through anchored descriptors."""

        return _descriptor.read_bounded_regular_file(
            self._job_fd, raw_path, max_bytes=max_bytes
        )

    def invalidate_file(self, raw_path: str) -> None:
        """Remove one existing regular artifact through anchored descriptors."""

        parts = _descriptor.parse_artifact_parts(raw_path)
        root_fd = _descriptor.duplicate_job_fd(self._job_fd, raw_path)
        current_fd = root_fd
        try:
            for component in parts[:-1]:
                next_fd = _descriptor.open_existing_directory(
                    current_fd, component, raw_path
                )
                if next_fd is None:
                    return
                os.close(current_fd)
                current_fd = next_fd
            try:
                entry_stat = os.lstat(parts[-1], dir_fd=current_fd)
            except FileNotFoundError:
                return
            if stat.S_ISLNK(entry_stat.st_mode):
                raise SandboxArtifactPathError(raw_path)
            try:
                os.unlink(parts[-1], dir_fd=current_fd)
                os.fsync(current_fd)
            except OSError as exc:
                raise SandboxArtifactPathError(raw_path) from exc
        finally:
            os.close(current_fd)

    def close(self) -> None:
        """Release the anchored job-directory descriptor."""

        job_fd = self._job_fd
        self._job_fd = -1
        _descriptor.close_fd(job_fd)

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
