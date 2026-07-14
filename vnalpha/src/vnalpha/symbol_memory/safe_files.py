from __future__ import annotations

import os
from pathlib import Path


class _PathIdentityChangedError(OSError):
    pass


def _directory_identity(path: Path) -> tuple[int, int]:
    try:
        state = os.stat(path)
    except OSError as exc:
        raise _PathIdentityChangedError(
            "Knowledge directory identity changed during write."
        ) from exc
    return (state.st_dev, state.st_ino)


def _assert_path_identity(path: Path, expected_identity: tuple[int, int]) -> None:
    if _directory_identity(path) != expected_identity:
        raise _PathIdentityChangedError(
            "Knowledge directory identity changed during write."
        )


def atomic_replace(source: Path, destination: Path) -> None:
    target_directory = destination.parent
    directory_identity = _directory_identity(target_directory)
    directory_descriptor = os.open(target_directory, os.O_RDONLY)
    try:
        os.replace(source, destination)
        try:
            _assert_path_identity(target_directory, directory_identity)
        except _PathIdentityChangedError:
            try:
                os.unlink(destination.name, dir_fd=directory_descriptor)
            except FileNotFoundError:
                pass
            raise
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


__all__ = ["_PathIdentityChangedError", "atomic_replace"]
