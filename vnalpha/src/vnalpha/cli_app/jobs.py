from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, NoReturn, assert_never

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
)

app = typer.Typer(help="Inspect and administer durable provisioning jobs.")


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
    job = _job(_queue(queue_path), job_id)
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


def _job(queue: ProvisioningQueue, value: str) -> ProvisioningJob:
    try:
        job = queue.get(ProvisioningJobId(value))
    except ProvisioningQueueError as error:
        _queue_error(error)
    if job is None:
        raise typer.BadParameter("Unknown provisioning job.")
    return job


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


def _job_line(job: ProvisioningJob) -> str:
    payload = _job_payload(job)
    return (
        f"{payload['status']} job={payload['job_id']} stage={payload['stage']} "
        f"priority={payload['priority']} elapsed={payload['elapsed_seconds']}s "
        f"result={payload['result'] or '-'} error={payload['error'] or '-'}"
    )


__all__ = ["app"]
