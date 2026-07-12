from __future__ import annotations

import json
import multiprocessing
import os
import time
from pathlib import Path

import duckdb
import pytest

from vnalpha.warehouse.migrations import run_migrations


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


def test_optional_date_resolution_is_distinct_from_explicit_validation() -> None:
    from datetime import date

    from vnalpha.data_availability.dates import (
        InvalidEnsureDateError,
        normalize_explicit_date,
        normalize_optional_date,
    )

    expected = date(2026, 7, 10)
    assert normalize_optional_date(None, today=expected) == "2026-07-10"
    assert normalize_optional_date("today", today=expected) == "2026-07-10"
    with pytest.raises(InvalidEnsureDateError):
        normalize_explicit_date("today")


def test_data_lock_releases_owner_after_exception(tmp_path: Path) -> None:
    from vnalpha.data_availability.lock import EnsureLock

    lock = EnsureLock("FPT", "2026-07-10", lock_dir=tmp_path)
    with pytest.raises(RuntimeError, match="provisioning failed"):
        with lock:
            raise RuntimeError("provisioning failed")
    assert not lock.lock_path.exists()


def test_data_lock_context_manager_never_enters_without_ownership(
    tmp_path: Path,
) -> None:
    from vnalpha.data_availability.lock import EnsureLock

    owner = EnsureLock("FPT", "2026-07-10", lock_dir=tmp_path)
    contender = EnsureLock("FPT", "2026-07-10", lock_dir=tmp_path)
    assert owner.acquire()
    entered = False
    with pytest.raises(RuntimeError, match="already active"):
        with contender:
            entered = True
    assert entered is False
    owner.release()


def test_data_lock_keeps_untrusted_symbol_inside_lock_directory(
    tmp_path: Path,
) -> None:
    from vnalpha.data_availability.lock import EnsureLock

    lock = EnsureLock("ABC/../../escaped", "2026-07-10", lock_dir=tmp_path)
    assert lock.lock_path.parent == tmp_path
    assert lock.acquire()
    lock.release()

    unsafe_date = EnsureLock("FPT", "2026/../../escaped", lock_dir=tmp_path)
    assert unsafe_date.lock_path.parent == tmp_path
    assert unsafe_date.acquire()
    unsafe_date.release()


def test_invalid_command_date_has_actionable_user_error() -> None:
    from vnalpha.commands.errors import CommandValidationError
    from vnalpha.commands.normalizers import normalize_date

    with pytest.raises(
        CommandValidationError,
        match="Expected 'today' or ISO format YYYY-MM-DD",
    ):
        normalize_date("2026-13-40")


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


def test_stale_owner_cannot_release_replacement_lock(tmp_path: Path) -> None:
    from vnalpha.data_availability.lock import EnsureLock

    # Given: a stale lock is replaced by a new owner.
    stale = EnsureLock("FPT", "2026-07-10", lock_dir=tmp_path, stale_seconds=1)
    assert stale.acquire() is True
    old_time = time.time() - 10
    os.utime(stale.lock_path, (old_time, old_time))
    replacement = EnsureLock("FPT", "2026-07-10", lock_dir=tmp_path, stale_seconds=1)
    assert replacement.acquire() is True
    replacement_payload = json.loads(replacement.lock_path.read_text(encoding="utf-8"))

    # When: the stale owner attempts its normal release path.
    stale.release()

    # Then: the replacement lock and owner token remain intact.
    assert replacement.lock_path.exists()
    current_payload = json.loads(replacement.lock_path.read_text(encoding="utf-8"))
    assert current_payload["owner_token"] == replacement_payload["owner_token"]
    assert current_payload["pid"] == os.getpid()
    replacement.release()


@pytest.mark.filterwarnings(
    "ignore:This process .* is multi-threaded, use of fork\\(\\) may lead to "
    "deadlocks in the child.:DeprecationWarning"
)
def test_stale_lock_replacement_has_one_process_owner(tmp_path: Path) -> None:
    from vnalpha.data_availability.lock import EnsureLock

    # Given: two processes contend for the same artificially stale owner file.
    stale = EnsureLock("FPT", "2026-07-10", lock_dir=tmp_path, stale_seconds=1)
    assert stale.acquire() is True
    old_time = time.time() - 10
    os.utime(stale.lock_path, (old_time, old_time))
    context = multiprocessing.get_context("fork")
    start = context.Event()
    release = context.Event()
    results = context.Queue()
    workers = [
        context.Process(
            target=_acquire_contended_lock,
            args=(str(tmp_path), start, release, results, 1),
        )
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()

    # When: both replacement attempts begin and the stale owner releases afterward.
    start.set()
    acquisitions = [results.get(timeout=5), results.get(timeout=5)]
    stale.release()

    # Then: one replacement remains owned until its process releases it.
    assert sorted(acquisitions) == [False, True]
    assert stale.lock_path.exists()
    release.set()
    for worker in workers:
        worker.join(timeout=5)
    assert all(worker.exitcode == 0 for worker in workers)


def test_invalid_explicit_date_fails_before_lock_or_actions(tmp_path: Path) -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
    from vnalpha.data_availability.policy import DataAvailabilityPolicy

    # Given: every provisioning dependency records any side effect.
    conn = duckdb.connect()
    run_migrations(conn=conn)
    calls: list[str] = []

    def record_action(_conn, **_kwargs):
        calls.append("action")
        return {"inserted": 0, "upserted": 0, "built": 0}

    lock_dir = tmp_path / "locks"

    # When: an explicit impossible date crosses the ensure boundary.
    with pytest.raises(ValueError, match="Invalid target date '2026-13-40'"):
        ensure_symbol_analysis_ready(
            conn,
            "FPT",
            "2026-13-40",
            policy=DataAvailabilityPolicy(auto_sync=True),
            _lock_dir=lock_dir,
            _sync_symbols_fn=record_action,
            _sync_ohlcv_fn=record_action,
            _sync_index_fn=record_action,
            _build_canonical_fn=record_action,
            _build_features_fn=record_action,
            _score_universe_fn=record_action,
        )

    # Then: validation precedes lock creation, queries, syncs, builds, and scoring.
    assert calls == []
    assert not lock_dir.exists()
