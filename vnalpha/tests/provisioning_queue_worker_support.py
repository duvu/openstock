from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.provisioning_queue import (
    EnsureCurrentSymbolGoal,
    QueueDataset,
    QueueEntityType,
    SyncDatasetRangeGoal,
)
from vnalpha.provisioning_queue.handlers import (
    HandlerResult,
    ProvisioningGoalStage,
    ProvisioningStage,
)
from vnalpha.provisioning_queue.models import GoalType, ProvisioningGoal
from vnalpha.provisioning_queue.queue_models import (
    ProvisioningJob,
    ProvisioningJobId,
)
from vnalpha.provisioning_queue.repository import ProvisioningQueue


@dataclass(frozen=True, slots=True)
class StagedHandler:
    stage_definitions: tuple[ProvisioningGoalStage, ...]
    goal_type: GoalType = GoalType.ENSURE_CURRENT_SYMBOL

    def stages(self, _: ProvisioningGoal) -> tuple[ProvisioningGoalStage, ...]:
        return self.stage_definitions


class CrashBeforeCompletionQueue(ProvisioningQueue):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._crash_once = True

    def complete(
        self, job_id: ProvisioningJobId, worker_id: str, result: str
    ) -> ProvisioningJob:
        if self._crash_once:
            self._crash_once = False
            raise KeyboardInterrupt
        return super().complete(job_id, worker_id, result)


class CancelBeforeCompletionQueue(ProvisioningQueue):
    def complete(
        self, job_id: ProvisioningJobId, worker_id: str, result: str
    ) -> ProvisioningJob:
        self.cancel(job_id)
        return super().complete(job_id, worker_id, result)


class CancelBeforeFailureQueue(ProvisioningQueue):
    def fail(
        self, job_id: ProvisioningJobId, worker_id: str, error: str
    ) -> ProvisioningJob:
        self.cancel(job_id)
        return super().fail(job_id, worker_id, error)


def current_goal(symbol: str) -> EnsureCurrentSymbolGoal:
    return EnsureCurrentSymbolGoal(
        symbol=symbol,
        effective_date=date(2026, 7, 21),
        desired_capability=ReadinessCapability.PRICE_ANALYSIS,
        source_policy_version="policy-v1",
        contract_version="current-symbol-v1",
    )


def range_goal(entity_id: str) -> SyncDatasetRangeGoal:
    return SyncDatasetRangeGoal(
        dataset=QueueDataset.INDEX_OHLCV,
        entity_type=QueueEntityType.INDEX,
        entity_id=entity_id,
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 21),
        source_policy_version="policy-v1",
        contract_version="dataset-range-v1",
    )


def stage(
    name: str,
    requires_warehouse_write: bool,
    action: Callable[[duckdb.DuckDBPyConnection | None], HandlerResult],
) -> ProvisioningStage:
    return ProvisioningStage(name, requires_warehouse_write, action)
