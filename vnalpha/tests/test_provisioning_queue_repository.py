from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier

import pytest

from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.provisioning_queue import (
    EnsureCurrentSymbolGoal,
    FinalizeMarketSessionGoal,
    GoalEnrichment,
    ProvisioningJobId,
    ProvisioningJobLeaseError,
    ProvisioningJobNotFoundError,
    ProvisioningJobStatus,
    ProvisioningQueue,
    ProvisioningQueueStorageError,
    ProvisioningQueueValidationError,
    QueueDataset,
    QueueEntityType,
    RefreshMode,
    SyncDatasetRangeGoal,
)


def test_durable_provisioning_queue_contract(tmp_path) -> None:
    now = datetime(2030, 7, 21, 9, tzinfo=UTC)
    symbol_goal = EnsureCurrentSymbolGoal(
        symbol="FPT",
        effective_date=date(2026, 7, 21),
        desired_capability=ReadinessCapability.CANDIDATE_RANKING,
        allowed_fallback=ReadinessCapability.PRICE_ANALYSIS,
        requested_enrichments=(
            GoalEnrichment.VALUATION_CONTEXT,
            GoalEnrichment.FUNDAMENTAL_CONTEXT,
        ),
        refresh_mode=RefreshMode.CACHE_FIRST,
        source_policy_version="policy-v1",
        contract_version="current-symbol-v1",
    )
    range_goal = SyncDatasetRangeGoal(
        dataset=QueueDataset.INDEX_OHLCV,
        entity_type=QueueEntityType.INDEX,
        entity_id="VNINDEX",
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 21),
        refresh_mode=RefreshMode.FORCE_REFRESH,
        source_policy_version="policy-v1",
        contract_version="dataset-range-v1",
    )
    finalization_goal = FinalizeMarketSessionGoal(
        maintenance_run_id="maintenance-2026-07-21",
        resolved_session=date(2026, 7, 21),
        frozen_universe_hash="universe-v1",
        source_policy_version="policy-v1",
        finalization_contract_version="finalization-v1",
    )
    queue = ProvisioningQueue(tmp_path / "provisioning.sqlite3", max_attempts=2)

    settings = queue.initialize()
    submitted_symbol = queue.submit_or_join(
        symbol_goal, priority=5, origin="interactive", now=now
    )
    submitted_range = queue.submit_or_join(range_goal, priority=3, now=now)
    submitted_finalization = queue.submit_or_join(
        finalization_goal, priority=1, now=now
    )
    joined_symbol = queue.submit_or_join(
        symbol_goal.model_copy(
            update={
                "requested_enrichments": (
                    GoalEnrichment.FUNDAMENTAL_CONTEXT,
                    GoalEnrichment.VALUATION_CONTEXT,
                    GoalEnrichment.FUNDAMENTAL_CONTEXT,
                )
            }
        ),
        priority=9,
        correlation_id="maintenance-and-interactive",
        now=now,
    )

    assert settings.journal_mode == "WAL"
    assert settings.foreign_keys_enabled
    assert settings.busy_timeout_ms == 1_000
    assert settings.synchronous in {"NORMAL", "FULL", "EXTRA"}
    migration_path = tmp_path / "migration.sqlite3"
    with sqlite3.connect(migration_path) as connection:
        connection.execute("PRAGMA user_version = 0")
    migrated_queue = ProvisioningQueue(migration_path)
    migrated_queue.initialize()
    assert not migrated_queue.list()
    with sqlite3.connect(migration_path) as connection:
        connection.execute("PRAGMA user_version = 2")
    with pytest.raises(ProvisioningQueueStorageError):
        migrated_queue.initialize()
    with pytest.raises(ProvisioningJobNotFoundError):
        queue.cancel(ProvisioningJobId("unknown-job"))
    assert [job.goal for job in queue.list()] == [
        symbol_goal,
        range_goal,
        finalization_goal,
    ]
    assert joined_symbol.joined_existing_job
    assert joined_symbol.job.job_id == submitted_symbol.job.job_id
    assert joined_symbol.job.priority == 9

    claimed_symbol = queue.claim("worker-symbol", now=now)
    assert claimed_symbol is not None
    assert claimed_symbol.job_id == submitted_symbol.job.job_id
    assert claimed_symbol.status is ProvisioningJobStatus.RUNNING
    assert (
        queue.heartbeat(
            claimed_symbol.job_id, "worker-symbol", now=now + timedelta(seconds=10)
        ).lease_owner
        == "worker-symbol"
    )
    assert queue.cancel(claimed_symbol.job_id).cancellation_requested
    assert queue.requeue_expired(now=now + timedelta(seconds=71))
    assert queue.get(claimed_symbol.job_id).status is ProvisioningJobStatus.CANCELLED
    assert (
        queue.cancel(submitted_range.job.job_id).status
        is ProvisioningJobStatus.CANCELLED
    )

    claimed_finalization = queue.claim("worker-finalization", now=now)
    assert claimed_finalization is not None
    assert claimed_finalization.job_id == submitted_finalization.job.job_id
    completed = queue.complete(
        claimed_finalization.job_id,
        "worker-finalization",
        "persisted evidence is already current",
    )
    with pytest.raises(ProvisioningQueueValidationError):
        queue.complete(claimed_finalization.job_id, "worker-finalization", "x" * 2_049)
    assert completed.status is ProvisioningJobStatus.SUCCEEDED
    assert completed.result == "persisted evidence is already current"

    recovery_now = datetime(2020, 1, 1, tzinfo=UTC)
    recovery_queue = ProvisioningQueue(
        tmp_path / "recovery.sqlite3", lease_seconds=30, max_attempts=2
    )
    recovery_queue.initialize()
    recovery_job = recovery_queue.submit_or_join(
        symbol_goal, priority=1, now=recovery_now
    ).job
    first_lease = recovery_queue.claim("worker-one", now=recovery_now)
    assert first_lease is not None
    assert first_lease.job_id == recovery_job.job_id
    with pytest.raises(ProvisioningJobLeaseError):
        recovery_queue.complete(first_lease.job_id, "worker-one", "stale completion")
    assert recovery_queue.requeue_expired(now=recovery_now + timedelta(seconds=31))
    second_lease = recovery_queue.claim(
        "worker-two", now=recovery_now + timedelta(seconds=31)
    )
    assert second_lease is not None
    assert second_lease.attempts == 2
    recovered = recovery_queue.requeue_expired(now=recovery_now + timedelta(seconds=62))
    recovered_job = recovery_queue.get(recovery_job.job_id)
    assert recovered_job in recovered
    assert recovered_job is not None
    assert recovered_job.status is ProvisioningJobStatus.FAILED

    concurrent_queue = ProvisioningQueue(tmp_path / "concurrent.sqlite3")
    concurrent_queue.initialize()
    concurrent_job = concurrent_queue.submit_or_join(
        symbol_goal, priority=1, now=now
    ).job
    barrier = Barrier(4)

    def submit():
        barrier.wait()
        return concurrent_queue.submit_or_join(symbol_goal, priority=2, now=now)

    def claim(worker_id: str):
        barrier.wait()
        return concurrent_queue.claim(worker_id, now=now)

    def get():
        barrier.wait()
        return concurrent_queue.get(concurrent_job.job_id)

    with ThreadPoolExecutor(max_workers=4) as executor:
        joined, first_claim, second_claim, read = tuple(
            executor.map(
                lambda operation: operation(),
                (
                    submit,
                    lambda: claim("worker-a"),
                    lambda: claim("worker-b"),
                    get,
                ),
            )
        )

    assert joined.job.job_id == concurrent_job.job_id
    assert read is not None
    assert sum(job is not None for job in (first_claim, second_claim)) == 1
    assert concurrent_queue.list() == (concurrent_queue.get(concurrent_job.job_id),)
