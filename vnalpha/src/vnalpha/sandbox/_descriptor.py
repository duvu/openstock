"""Descriptor-relative primitives for contained sandbox artifacts."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import override


@dataclass(frozen=True, slots=True)
class SandboxArtifactPathError(ValueError):
    """An artifact path is not contained in the job's canonical directory."""

    path: str

    @override
    def __str__(self) -> str:
        return f"sandbox artifact path is unsafe: {self.path}"


@dataclass(frozen=True, slots=True)
class SandboxArtifactNotFoundError(ValueError):
    """A canonical sandbox artifact does not exist."""

    path: str

    @override
    def __str__(self) -> str:
        return f"sandbox artifact was not found: {self.path}"


@dataclass(frozen=True, slots=True)
class SandboxArtifactTypeError(ValueError):
    """A canonical sandbox artifact is not a regular file."""

    path: str

    @override
    def __str__(self) -> str:
        return f"sandbox artifact is not a regular file: {self.path}"


@dataclass(frozen=True, slots=True)
class SandboxArtifactSizeError(ValueError):
    """A canonical sandbox artifact exceeds its permitted size."""

    path: str
    max_bytes: int

    @override
    def __str__(self) -> str:
        return f"sandbox artifact exceeds the byte limit: {self.path}"


def parse_artifact_parts(raw_path: str) -> tuple[str, ...]:
    """Parse one canonical relative artifact path into descriptor components."""

    path = PurePosixPath(raw_path)
    windows_path = PureWindowsPath(raw_path)
    is_safe = (
        bool(path.parts)
        and not path.is_absolute()
        and not windows_path.is_absolute()
        and ".." not in path.parts
        and ".." not in windows_path.parts
        and raw_path != "."
        and "\\" not in raw_path
        and path.as_posix() == raw_path
    )
    if not is_safe:
        raise SandboxArtifactPathError(raw_path)
    return path.parts


def open_directory(path: Path, raw_path: str) -> int:
    """Open a trusted directory without following symlinks."""

    try:
        return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise SandboxArtifactPathError(raw_path) from exc


def open_or_create_directory(parent_fd: int, component: str, raw_path: str) -> int:
    """Open or create one descriptor-relative directory component."""

    try:
        os.mkdir(component, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        _ = os.lstat(component, dir_fd=parent_fd)
    try:
        return os.open(
            component,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise SandboxArtifactPathError(raw_path) from exc


def open_existing_directory(
    parent_fd: int, component: str, raw_path: str
) -> int | None:
    """Open one existing descriptor-relative directory component."""

    try:
        return os.open(
            component,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SandboxArtifactPathError(raw_path) from exc


def duplicate_job_fd(job_fd: int, raw_path: str) -> int:
    """Duplicate an open job-directory descriptor or reject closed storage."""

    if job_fd < 0:
        raise SandboxArtifactPathError(raw_path)
    try:
        return os.dup(job_fd)
    except OSError as exc:
        raise SandboxArtifactPathError(raw_path) from exc


def close_fd(fd: int | None) -> None:
    """Close one valid descriptor."""

    if fd is not None and fd >= 0:
        os.close(fd)


def read_bounded_regular_file(job_fd: int, raw_path: str, *, max_bytes: int) -> bytes:
    """Read one contained regular file without following paths or exceeding a limit."""

    parts = parse_artifact_parts(raw_path)
    current_fd = duplicate_job_fd(job_fd, raw_path)
    leaf_fd: int | None = None
    try:
        for component in parts[:-1]:
            next_fd = open_existing_directory(current_fd, component, raw_path)
            if next_fd is None:
                raise SandboxArtifactNotFoundError(raw_path)
            os.close(current_fd)
            current_fd = next_fd
        try:
            leaf_fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=current_fd,
            )
        except FileNotFoundError as exc:
            raise SandboxArtifactNotFoundError(raw_path) from exc
        except OSError as exc:
            raise SandboxArtifactTypeError(raw_path) from exc
        try:
            entry_stat = os.fstat(leaf_fd)
        except OSError as exc:
            raise SandboxArtifactTypeError(raw_path) from exc
        if not stat.S_ISREG(entry_stat.st_mode):
            raise SandboxArtifactTypeError(raw_path)
        if entry_stat.st_size > max_bytes:
            raise SandboxArtifactSizeError(raw_path, max_bytes)
        content = bytearray()
        while len(content) <= max_bytes:
            try:
                chunk = os.read(leaf_fd, min(65_536, max_bytes + 1 - len(content)))
            except OSError as exc:
                raise SandboxArtifactTypeError(raw_path) from exc
            if not chunk:
                return bytes(content)
            content.extend(chunk)
        raise SandboxArtifactSizeError(raw_path, max_bytes)
    finally:
        close_fd(leaf_fd)
        close_fd(current_fd)
