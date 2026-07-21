from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest


def _acquire_contended_lock(
    lock_dir: str,
    start: multiprocessing.synchronize.Event,
    release: multiprocessing.synchronize.Event,
    results: multiprocessing.queues.Queue,
    stale_seconds: float = 300,
) -> None:
    from vnalpha.data_availability.lock import EnsureLock

    start.wait(timeout=5)
    lock = EnsureLock(
        "FPT",
        "2026-07-10",
        lock_dir=Path(lock_dir),
        stale_seconds=stale_seconds,
    )
    acquired = lock.acquire()
    results.put(acquired)
    if acquired:
        release.wait(timeout=5)
        lock.release()


@pytest.mark.filterwarnings(
    "ignore:This process .* is multi-threaded, use of fork\\(\\) may lead to "
    "deadlocks in the child.:DeprecationWarning"
)
def test_data_lock_has_exactly_one_process_owner_under_contention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: both legacy contenders are forced past the check-before-write window.
    context = multiprocessing.get_context("fork")
    check_barrier = context.Barrier(2)
    original_exists = Path.exists

    def synchronized_exists(path: Path) -> bool:
        if path.name == "data-ensure-FPT-2026-07-10.lock":
            check_barrier.wait(timeout=5)
            return False
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", synchronized_exists)
    start = context.Event()
    release = context.Event()
    results = context.Queue()
    workers = [
        context.Process(
            target=_acquire_contended_lock,
            args=(str(tmp_path), start, release, results),
        )
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()

    # When: both processes attempt acquisition concurrently.
    start.set()
    acquisitions = [results.get(timeout=5), results.get(timeout=5)]
    release.set()
    for worker in workers:
        worker.join(timeout=5)

    # Then: atomic acquisition allows exactly one provisioning owner.
    assert sorted(acquisitions) == [False, True]
    assert all(worker.exitcode == 0 for worker in workers)
