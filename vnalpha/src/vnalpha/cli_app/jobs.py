from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, NoReturn, assert_never

import duckdb
import typer

from vnalpha.data_provisioning.current_symbol_queue_wait import (
    CurrentSymbolWaitMode,
    wait_for_terminal,
)
from vnalpha.provisioning_queue import (
    DEFAULT_QUEUE_PATH,
    ProvisioningJob,
    ProvisioningJobId,
    ProvisioningJobStatus,
    ProvisioningQueue,
    ProvisioningQueueError,
    ProvisioningQueueStorageError,
    PrunedProvisioningJob,
    QueueCheckpointResult,
    QueueHealthReport,
    QueuePruneResult,
)
from vnalpha.warehouse.connection import WarehouseOpenError, read_connection

app = typer.Typer(help="Inspect and administer durable provisioning jobs.")


@app.command("health")
def health(
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Inspect a queue without creating, repairing, or claiming work."""
    report = ProvisioningQueue(queue_path).health()
    payload = _health_payload(report)
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
        raise typer.Exit(code=0 if report.can_claim else 1)
    typer.echo(
        "HEALTH "
        f"claimable={str(report.can_claim).lower()} "
        f"schema={report.schema_version} integrity={report.integrity_check} "
        f"queued={report.queue_depth} active_leases={report.active_leases} "
        f"expired_leases={report.expired_leases}"
    )
    if report.detail:
        typer.echo(f"detail={report.detail}", err=True)
    if not report.can_claim:
        raise typer.Exit(code=1)


@app.command("checkpoint")
def checkpoint(
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run one passive WAL checkpoint without interrupting queue readers."""
    queue = _queue(queue_path)
    try:
        result = queue.checkpoint()
    except ProvisioningQueueError as error:
        _queue_error(error)
    payload = _checkpoint_payload(result)
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
        return
    typer.echo(
        "CHECKPOINT "
        f"busy_readers={result.busy_readers} wal_frames={result.wal_frames} "
        f"checkpointed_frames={result.checkpointed_frames}"
    )


@app.command("prune")
def prune(
    older_than_days: Annotated[int, typer.Option("--older-than", min=1, max=3_650)],
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    warehouse_path: Annotated[Path | None, typer.Option("--warehouse-path")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Prune one bounded batch while retaining all maintenance-linked jobs."""
    queue = _queue(queue_path)
    try:
        result = queue.prune(
            older_than_days=older_than_days,
            retained_job_ids=_retained_maintenance_job_ids(warehouse_path),
        )
    except ProvisioningQueueError as error:
        _queue_error(error)
    payload = _prune_payload(result)
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
        return
    typer.echo(
        "PRUNE "
        f"succeeded={result.pruned_succeeded} failed={result.pruned_failed} "
        f"cancelled={result.pruned_cancelled} "
        f"retained_referenced={result.retained_referenced}"
    )


@app.command("list")
def list_jobs(
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    status: Annotated[ProvisioningJobStatus | None, typer.Option("--status")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List bounded queue state without opening the research warehouse."""
    queue = _queue(queue_path)
    try:
        jobs = queue.list(status=status)
    except ProvisioningQueueError as error:
        _queue_error(error)
    if json_output:
        typer.echo(json.dumps([_job_payload(job) for job in jobs], sort_keys=True))
        return
    for job in jobs:
        typer.echo(_job_line(job))


@app.command("status")
def status(
    job_id: str,
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show the bounded lifecycle result for one provisioning job."""
    queue = _queue(queue_path)
    job = _job(queue, job_id, required=False)
    if job is None:
        pruned = _pruned_job(queue, job_id)
        if pruned is None:
            raise typer.BadParameter("Unknown provisioning job.")
        payload = _pruned_payload(pruned)
        if json_output:
            typer.echo(json.dumps(payload, sort_keys=True))
            return
        typer.echo(
            f"PRUNED job={payload['job_id']} final_status={payload['final_status']} "
            f"pruned_at={payload['pruned_at']}"
        )
        return
    if json_output:
        typer.echo(json.dumps(_job_payload(job), sort_keys=True))
        return
    typer.echo(_job_line(job))


@app.command("wait")
def wait(
    job_id: str,
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    timeout_seconds: Annotated[float | None, typer.Option("--timeout", min=0)] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Wait without holding a DuckDB connection or cancelling shared work."""
    queue = _queue(queue_path)
    job = _job(queue, job_id)
    mode = (
        CurrentSymbolWaitMode.WAIT_UNTIL_TERMINAL
        if timeout_seconds is None
        else CurrentSymbolWaitMode.WAIT_UP_TO
    )
    try:
        completed = wait_for_terminal(queue, job, mode, timeout_seconds or 0)
    except ProvisioningQueueError as error:
        _queue_error(error)
    if json_output:
        typer.echo(json.dumps(_job_payload(completed), sort_keys=True))
        return
    typer.echo(_job_line(completed))


@app.command("cancel")
def cancel(
    job_id: str,
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    confirm: Annotated[bool, typer.Option("--confirm")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Request administrative cancellation after an explicit shared-job warning."""
    queue = _queue(queue_path)
    job = _job(queue, job_id)
    if not confirm:
        typer.echo(
            "WARNING: cancellation can affect every caller sharing this active job. "
            "Re-run with --confirm to request administrative cancellation.",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        cancelled = queue.cancel(job.job_id)
    except ProvisioningQueueError as error:
        _queue_error(error)
    if json_output:
        typer.echo(json.dumps(_job_payload(cancelled), sort_keys=True))
        return
    typer.echo(_job_line(cancelled))


@app.command("retry")
def retry(
    job_id: str,
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Create one bounded retry from a failed or cancelled typed job."""
    queue = _queue(queue_path)
    job = _job(queue, job_id)
    try:
        match job.status:
            case ProvisioningJobStatus.FAILED | ProvisioningJobStatus.CANCELLED:
                submission = queue.submit_or_join(
                    job.goal,
                    priority=job.priority,
                    origin=job.origin,
                    correlation_id=job.correlation_id,
                )
            case ProvisioningJobStatus.QUEUED | ProvisioningJobStatus.RUNNING:
                raise typer.BadParameter("Only terminal jobs can be retried.")
            case ProvisioningJobStatus.SUCCEEDED:
                raise typer.BadParameter("Successful jobs cannot be retried.")
            case unreachable:
                assert_never(unreachable)
    except ProvisioningQueueError as error:
        _queue_error(error)
    if json_output:
        typer.echo(json.dumps(_job_payload(submission.job), sort_keys=True))
        return
    typer.echo(_job_line(submission.job))


def _queue(queue_path: Path) -> ProvisioningQueue:
    queue = ProvisioningQueue(queue_path)
    try:
        queue.initialize()
    except ProvisioningQueueError as error:
        _queue_error(error)
    return queue


def _job(
    queue: ProvisioningQueue, value: str, *, required: bool = True
) -> ProvisioningJob | None:
    try:
        job = queue.get(ProvisioningJobId(value))
    except ProvisioningQueueError as error:
        _queue_error(error)
    if job is None and required:
        raise typer.BadParameter("Unknown provisioning job.")
    return job


def _pruned_job(queue: ProvisioningQueue, value: str) -> PrunedProvisioningJob | None:
    try:
        return queue.get_pruned(ProvisioningJobId(value))
    except ProvisioningQueueError as error:
        _queue_error(error)


def _retained_maintenance_job_ids(
    warehouse_path: Path | None,
) -> frozenset[ProvisioningJobId]:
    try:
        with read_connection(warehouse_path) as connection:
            rows = connection.execute(
                "SELECT DISTINCT job_id FROM maintenance_run_job "
                "WHERE job_id IS NOT NULL"
            ).fetchall()
    except duckdb.CatalogException as error:
        raise ProvisioningQueueStorageError(
            "maintenance queue evidence is unavailable; run the explicit warehouse "
            "migration before pruning"
        ) from error
    except (duckdb.Error, WarehouseOpenError) as error:
        raise ProvisioningQueueStorageError(
            "could not verify retained maintenance job evidence"
        ) from error
    return frozenset(ProvisioningJobId(str(row[0])) for row in rows)


def _queue_error(error: ProvisioningQueueError) -> NoReturn:
    typer.echo(f"Jobs command failed: {error}", err=True)
    raise typer.Exit(code=1) from error


def _job_payload(job: ProvisioningJob) -> dict[str, str | int | bool | None]:
    return {
        "job_id": str(job.job_id),
        "goal_identity": job.goal_identity,
        "goal_type": job.goal.goal_type.value,
        "status": job.status.value,
        "stage": job.stage,
        "priority": job.priority,
        "attempts": job.attempts,
        "origin": job.origin,
        "correlation_id": job.correlation_id,
        "cancellation_requested": job.cancellation_requested,
        "elapsed_seconds": int(
            max((datetime.now(UTC) - job.created_at).total_seconds(), 0)
        ),
        "result": job.result,
        "error": job.error,
    }


def _pruned_payload(job: PrunedProvisioningJob) -> dict[str, str]:
    return {
        "job_id": str(job.job_id),
        "status": "PRUNED",
        "final_status": job.final_status.value,
        "pruned_at": job.pruned_at.isoformat(),
    }


def _health_payload(report: QueueHealthReport) -> dict[str, str | int | bool | None]:
    return {
        "can_claim": report.can_claim,
        "schema_version": report.schema_version,
        "supported_schema": report.supported_schema,
        "integrity_check": report.integrity_check,
        "integrity_ok": report.integrity_ok,
        "journal_mode": report.journal_mode,
        "synchronous": report.synchronous,
        "busy_timeout_ms": report.busy_timeout_ms,
        "file_size_bytes": report.file_size_bytes,
        "wal_size_bytes": report.wal_size_bytes,
        "disk_free_bytes": report.disk_free_bytes,
        "disk_free_threshold_bytes": report.disk_free_threshold_bytes,
        "disk_free_above_threshold": report.disk_free_above_threshold,
        "readable": report.readable,
        "writable": report.writable,
        "active_leases": report.active_leases,
        "expired_leases": report.expired_leases,
        "queue_depth": report.queue_depth,
        "oldest_queued_age_seconds": report.oldest_queued_age_seconds,
        "last_checkpoint_at": _timestamp(report.last_checkpoint_at),
        "last_prune_at": _timestamp(report.last_prune_at),
        "last_migration_at": _timestamp(report.last_migration_at),
        "detail": report.detail,
    }


def _checkpoint_payload(result: QueueCheckpointResult) -> dict[str, str | int]:
    return {
        "busy_readers": result.busy_readers,
        "wal_frames": result.wal_frames,
        "checkpointed_frames": result.checkpointed_frames,
        "completed_at": result.completed_at.isoformat(),
    }


def _prune_payload(result: QueuePruneResult) -> dict[str, str | int]:
    return {
        "pruned_succeeded": result.pruned_succeeded,
        "pruned_failed": result.pruned_failed,
        "pruned_cancelled": result.pruned_cancelled,
        "retained_referenced": result.retained_referenced,
        "completed_at": result.completed_at.isoformat(),
    }


def _timestamp(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _job_line(job: ProvisioningJob) -> str:
    payload = _job_payload(job)
    return (
        f"{payload['status']} job={payload['job_id']} stage={payload['stage']} "
        f"priority={payload['priority']} elapsed={payload['elapsed_seconds']}s "
        f"result={payload['result'] or '-'} error={payload['error'] or '-'}"
    )


__all__ = ["app"]
