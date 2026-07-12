"""Descriptor-relative atomic file replacement primitives."""

from __future__ import annotations

import os
from typing import Final
from uuid import uuid4

_TEMP_PREFIX: Final = ".sandbox-artifact-"


def write_atomic_file(
    parent_fd: int,
    name: str,
    content: bytes,
    *,
    mode: int = 0o600,
) -> None:
    """Atomically replace one file within an already-open directory descriptor."""

    temporary_name = f"{_TEMP_PREFIX}{uuid4().hex}"
    temporary_created = False
    try:
        temporary_fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            mode=mode,
            dir_fd=parent_fd,
        )
        temporary_created = True
        try:
            os.fchmod(temporary_fd, mode)
            _write_all(temporary_fd, content)
            os.fsync(temporary_fd)
        finally:
            os.close(temporary_fd)
        os.replace(
            temporary_name,
            name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        os.fsync(parent_fd)
    except OSError:
        if temporary_created:
            _remove_temporary_file(parent_fd, temporary_name)
        raise


def _write_all(fd: int, content: bytes) -> None:
    """Write all bytes to a regular descriptor."""

    written = 0
    while written < len(content):
        written += os.write(fd, content[written:])


def _remove_temporary_file(parent_fd: int, temporary_name: str) -> None:
    """Remove an unlinked-or-unreplaced temporary file after an I/O failure."""

    try:
        os.unlink(temporary_name, dir_fd=parent_fd)
    except FileNotFoundError:
        return
