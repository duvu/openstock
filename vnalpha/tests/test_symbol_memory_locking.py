from __future__ import annotations

import multiprocessing
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
