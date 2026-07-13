from __future__ import annotations

import json
import multiprocessing
import os
import time
from pathlib import Path

import pytest


def _contend_for_symbol_lock(
    root: str, result_queue: multiprocessing.Queue[str]
) -> None:
    from vnalpha.symbol_memory.locking import (
        MemoryLockContentionError,
        symbol_memory_lock,
    )

    try:
        with symbol_memory_lock(Path(root), "FPT"):
            result_queue.put("acquired")
    except MemoryLockContentionError:
        result_queue.put("contended")


def test_symbol_locks_are_independent_and_exclusive(tmp_path) -> None:
    from vnalpha.symbol_memory.locking import (
        MemoryLockContentionError,
        symbol_memory_lock,
    )

    with symbol_memory_lock(tmp_path, "FPT") as first:
        assert first.path.exists()
        with pytest.raises(MemoryLockContentionError):
            with symbol_memory_lock(tmp_path, "FPT"):
                pass
        with symbol_memory_lock(tmp_path, "HPG") as independent:
            assert independent.path.exists()

    assert not first.path.exists()


def test_root_maintenance_lock_serializes_bulk_operations(tmp_path) -> None:
    from vnalpha.symbol_memory.locking import (
        MemoryLockContentionError,
        root_maintenance_lock,
    )

    with root_maintenance_lock(tmp_path) as lock:
        assert lock.path.exists()
        with pytest.raises(MemoryLockContentionError):
            with root_maintenance_lock(tmp_path):
                pass

    assert not lock.path.exists()


def test_symbol_lock_excludes_another_process(tmp_path) -> None:
    from vnalpha.symbol_memory.locking import symbol_memory_lock

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    with symbol_memory_lock(tmp_path, "FPT"):
        worker = context.Process(
            target=_contend_for_symbol_lock,
            args=(str(tmp_path), result_queue),
        )
        worker.start()
        worker.join(timeout=10)

    assert worker.exitcode == 0
    assert result_queue.get(timeout=1) == "contended"


def test_stale_symbol_lock_owned_by_a_dead_process_is_reclaimed(tmp_path) -> None:
    from vnalpha.symbol_memory.locking import symbol_memory_lock

    lock_path = tmp_path / "knowledge" / "locks" / "symbols" / "FPT.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(json.dumps({"owner_pid": 999_999_999}), encoding="utf-8")
    stale_at = time.time() - 600
    os.utime(lock_path, (stale_at, stale_at))

    with symbol_memory_lock(tmp_path, "FPT") as lock:
        assert lock.path == lock_path
