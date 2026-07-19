from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from vnalpha.symbol_memory.models import MemoryEntity
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.storage import assert_knowledge_path, ensure_knowledge_layout


class MemoryLockContentionError(RuntimeError):
    pass


_STALE_LOCK_SECONDS = 300


@dataclass(frozen=True, slots=True)
class MemoryFileLock:
    path: Path
    owner_token: str


@contextmanager
def symbol_memory_lock(root: Path | None, symbol: str) -> Iterator[MemoryFileLock]:
    canonical_symbol = normalize_symbol(symbol)
    with _acquire_lock(root, "symbols", f"{canonical_symbol}.lock") as lock:
        yield lock


@contextmanager
def entity_memory_lock(
    root: Path | None, entity: MemoryEntity
) -> Iterator[MemoryFileLock]:
    category = entity.entity_type.value.lower()
    name = entity.entity_id.replace(":", "--") + ".lock"
    with _acquire_lock(root, category, name) as lock:
        yield lock


@contextmanager
def root_maintenance_lock(root: Path | None) -> Iterator[MemoryFileLock]:
    with _acquire_lock(root, "maintenance", "root.lock") as lock:
        yield lock


@contextmanager
def _acquire_lock(
    root: Path | None, category: str, name: str
) -> Iterator[MemoryFileLock]:
    lock_dir = ensure_knowledge_layout(root).root / "locks" / category
    assert_knowledge_path(root, lock_dir)
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / name
    assert_knowledge_path(root, path)
    owner_token = uuid4().hex
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError as error:
            if _reclaim_stale_lock(path):
                continue
            raise MemoryLockContentionError(
                f"Memory lock is already held: {path.name}"
            ) from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(
            {"owner_pid": os.getpid(), "owner_token": owner_token},
            handle,
            sort_keys=True,
        )
        handle.flush()
        os.fsync(handle.fileno())
    lock = MemoryFileLock(path=path, owner_token=owner_token)
    try:
        yield lock
    finally:
        _release(lock)


def _release(lock: MemoryFileLock) -> None:
    try:
        payload = json.loads(lock.path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return
    if payload.get("owner_token") == lock.owner_token:
        lock.path.unlink(missing_ok=True)


def _reclaim_stale_lock(path: Path) -> bool:
    try:
        if time.time() - path.stat().st_mtime < _STALE_LOCK_SECONDS:
            return False
        payload = json.loads(path.read_text(encoding="utf-8"))
        owner_pid = int(payload["owner_pid"])
        os.kill(owner_pid, 0)
    except ProcessLookupError:
        path.unlink(missing_ok=True)
        return True
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return True
    except PermissionError:
        return False
    return False


__all__ = [
    "MemoryFileLock",
    "MemoryLockContentionError",
    "entity_memory_lock",
    "root_maintenance_lock",
    "symbol_memory_lock",
]
