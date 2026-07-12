from __future__ import annotations

import json
import os
import socket
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Iterator
from uuid import uuid4

if TYPE_CHECKING:
    from vnalpha.workspace_context.storage import WorkspacePaths


class WorkspaceLockError(RuntimeError):
    pass


class WorkspaceLockContentionError(WorkspaceLockError):
    def __init__(self, workspace_id: str, timeout_seconds: float) -> None:
        self.workspace_id = workspace_id
        self.timeout_seconds = timeout_seconds
        super().__init__()

    def __str__(self) -> str:
        return (
            f"Workspace {self.workspace_id} remained locked for "
            f"{self.timeout_seconds:.3f}s."
        )


@dataclass(frozen=True, slots=True)
class WorkspaceLockMetadata:
    workspace_id: str
    owner_token: str
    pid: int
    hostname: str
    created_at: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "workspace_id": self.workspace_id,
            "owner_token": self.owner_token,
            "pid": self.pid,
            "hostname": self.hostname,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceLock:
    path: Path
    metadata: WorkspaceLockMetadata


def read_lock_metadata(path: Path) -> WorkspaceLockMetadata | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return WorkspaceLockMetadata(
        workspace_id=str(payload["workspace_id"]),
        owner_token=str(payload["owner_token"]),
        pid=int(payload["pid"]),
        hostname=str(payload["hostname"]),
        created_at=str(payload["created_at"]),
    )


def _create_lock(path: Path, metadata: WorkspaceLockMetadata) -> bool:
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(metadata.to_dict(), handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    return True


def _remove_stale_lock(path: Path, stale_seconds: float) -> None:
    try:
        before = path.stat()
    except FileNotFoundError:
        return
    if time.time() - before.st_mtime <= stale_seconds:
        return
    try:
        after = path.stat()
    except FileNotFoundError:
        return
    if before.st_ino != after.st_ino or before.st_mtime_ns != after.st_mtime_ns:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        return


def acquire_lock(
    path: Path,
    workspace_id: str,
    *,
    timeout_seconds: float = 5.0,
    stale_seconds: float = 300.0,
) -> WorkspaceLock:
    metadata = WorkspaceLockMetadata(
        workspace_id=workspace_id,
        owner_token=uuid4().hex,
        pid=os.getpid(),
        hostname=socket.gethostname(),
        created_at=datetime.now(UTC).isoformat(),
    )
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        if _create_lock(path, metadata):
            return WorkspaceLock(path=path, metadata=metadata)
        _remove_stale_lock(path, stale_seconds)
        if time.monotonic() >= deadline:
            raise WorkspaceLockContentionError(workspace_id, timeout_seconds)
        time.sleep(min(0.01, max(deadline - time.monotonic(), 0.0)))


def release_lock(path: Path, owner_token: str) -> None:
    metadata = read_lock_metadata(path)
    if metadata is None or metadata.owner_token != owner_token:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        return


@contextmanager
def workspace_transaction(
    workspace_id: str,
    *,
    root: Path | None = None,
    timeout_seconds: float = 5.0,
    stale_seconds: float = 300.0,
) -> Iterator[WorkspacePaths]:
    from vnalpha.workspace_context.storage import ensure_workspace_layout

    paths = ensure_workspace_layout(root=root, workspace_id=workspace_id)
    lock = acquire_lock(
        paths.lock_path,
        workspace_id,
        timeout_seconds=timeout_seconds,
        stale_seconds=stale_seconds,
    )
    try:
        yield paths
    finally:
        release_lock(lock.path, lock.metadata.owner_token)
