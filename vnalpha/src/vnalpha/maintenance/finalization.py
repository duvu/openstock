from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from json import loads
from pathlib import Path

from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.provisioning_queue import (
    DEFAULT_QUEUE_PATH,
    FinalizeMarketSessionGoal,
    ProvisioningJobId,
    ProvisioningQueue,
    goal_identity,
)
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


@dataclass(frozen=True, slots=True)
class MaintenanceFinalizationResult:
    maintenance_run_id: str
    submitted: bool
    joined: bool
    job_id: ProvisioningJobId | None
    state: str
    correlation_id: str


def maybe_submit_session_finalization(
    maintenance_run_id: str,
    *,
    warehouse_path: Path | str | None = None,
    queue_path: Path = DEFAULT_QUEUE_PATH,
    priority: int = 0,
    correlation_id: str | None = None,
) -> MaintenanceFinalizationResult:
    correlation = _correlation_id(correlation_id)
    queue = ProvisioningQueue(queue_path)
    queue.initialize()
    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        run = connection.execute(
            "SELECT resolved_date, universe_hash, source_policy_version, status, expected_goals_json FROM maintenance_run WHERE run_id = ?",
            [maintenance_run_id],
        ).fetchone()
        if run is None:
            raise ValueError("Unknown maintenance run.")
        rows = connection.execute(
            "SELECT goal_type, job_id FROM maintenance_run_job WHERE maintenance_run_id = ? AND goal_type <> 'FINALIZE_MARKET_SESSION'",
            [maintenance_run_id],
        ).fetchall()
        expected_goals = loads(str(run[4]))
        if len(rows) != len(expected_goals) or any(row[1] is None for row in rows):
            return MaintenanceFinalizationResult(
                maintenance_run_id, False, False, None, "ACQUIRING", correlation
            )
        jobs = [queue.get(ProvisioningJobId(str(row[1]))) for row in rows]
        if any(job is None or not job.is_terminal for job in jobs):
            return MaintenanceFinalizationResult(
                maintenance_run_id, False, False, None, "ACQUIRING", correlation
            )
        existing = connection.execute(
            "SELECT job_id FROM maintenance_run_job WHERE maintenance_run_id = ? AND goal_type = 'FINALIZE_MARKET_SESSION'",
            [maintenance_run_id],
        ).fetchone()
        if existing is not None and existing[0] is not None:
            return MaintenanceFinalizationResult(
                maintenance_run_id,
                False,
                True,
                ProvisioningJobId(str(existing[0])),
                "FINALIZATION_QUEUED",
                correlation,
            )
        goal = FinalizeMarketSessionGoal(
            maintenance_run_id=maintenance_run_id,
            resolved_session=date.fromisoformat(str(run[0])),
            frozen_universe_hash=str(run[1]),
            source_policy_version=str(run[2]),
            finalization_contract_version="finalization-v1",
        )
        submission = queue.submit_or_join(
            goal,
            priority=priority,
            origin="maintenance-finalization",
            correlation_id=correlation,
        )
        connection.execute(
            "INSERT INTO maintenance_run_job (maintenance_run_id, goal_identity, goal_type, entity_id, goal_payload_json, job_id, mapped_at) VALUES (?, ?, ?, ?, ?, ?, current_timestamp)",
            [
                maintenance_run_id,
                goal_identity(goal),
                goal.goal_type.value,
                maintenance_run_id,
                goal.payload_json(),
                str(submission.job.job_id),
            ],
        )
        connection.execute(
            "UPDATE maintenance_run SET status = ? WHERE run_id = ?",
            ["FINALIZATION_QUEUED", maintenance_run_id],
        )
        return MaintenanceFinalizationResult(
            maintenance_run_id,
            not submission.joined_existing_job,
            submission.joined_existing_job,
            submission.job.job_id,
            "FINALIZATION_QUEUED",
            correlation,
        )


def _correlation_id(requested: str | None) -> str:
    if requested:
        return set_correlation_id(parent=requested)
    current = get_correlation_id()
    return current if current and current != "unset" else set_correlation_id()


__all__ = ["MaintenanceFinalizationResult", "maybe_submit_session_finalization"]
