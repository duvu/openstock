from __future__ import annotations

import json
from pathlib import Path

import typer

from vnalpha.closed_loop.errors import ClosedLoopBoundaryError, ClosedLoopError
from vnalpha.closed_loop.paths import resolve_component
from vnalpha.closed_loop.service import ClosedLoopService
from vnalpha.closed_loop.store import ClosedLoopStore
from vnalpha.observability.context import resolve_log_root

validate_app = typer.Typer(name="validate", help="Validate research artifacts.")
repair_app = typer.Typer(name="repair", help="Repair bounded research artifacts.")


@repair_app.command("prepare")
def repair_prepare(
    latest: bool = typer.Option(False, "--latest", help="Use the latest failed run"),
    run_id: str | None = typer.Option(None, "--run-id", help="Specific failed run ID"),
    output_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    from vnalpha.closed_loop.bundle import latest_failed_run

    root = resolve_log_root()
    if run_id:
        try:
            run_dir = resolve_component(root, "runs", run_id, "run_id")
        except ClosedLoopBoundaryError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    else:
        run_dir = latest_failed_run(root) if latest else None
    if run_dir is None or not run_dir.is_dir():
        typer.echo("Provide --latest or --run-id for an existing failed run.", err=True)
        raise typer.Exit(code=1)
    bundle = ClosedLoopService(ClosedLoopStore(root)).prepare_failed_run(run_dir)
    payload = bundle.model_dump(mode="json")
    if output_json:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"Repair bundle created: {bundle.repair_id}")
        typer.echo(f"Path: {root / 'bundles' / bundle.repair_id}")


@repair_app.command("status")
def repair_status(
    repair_id: str = typer.Argument(..., help="Repair bundle ID"),
    output_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    store = ClosedLoopStore(resolve_log_root())
    try:
        bundle = store.load_bundle(repair_id)
        lifecycle = store.current_lifecycle(repair_id)
        payload = {
            "repair_id": bundle.repair_id,
            "correlation_id": bundle.correlation_id,
            "state": lifecycle.state.value,
            "attempts": len(store.list_attempts(repair_id)),
        }
    except ClosedLoopError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_json:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"Repair: {payload['repair_id']}")
        typer.echo(f"State: {payload['state']}")
        typer.echo(f"Attempts: {payload['attempts']}")


@repair_app.command("propose")
def repair_propose(
    repair_id: str = typer.Argument(..., help="Repair bundle ID"),
    patch: str = typer.Option("", "--patch", help="Bounded research patch text"),
    scope: str = typer.Option(
        "sandbox_research_code", "--scope", help="Allowed research repair scope"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    from vnalpha.closed_loop.models import RepairScope

    try:
        proposal = ClosedLoopService(ClosedLoopStore(resolve_log_root())).propose(
            repair_id, scope=RepairScope(scope), patch=patch
        )
    except (ClosedLoopError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_json:
        typer.echo(proposal.model_dump_json(indent=2))
    else:
        typer.echo(f"Proposal: {proposal.proposal_id}")
        typer.echo(f"Accepted: {proposal.accepted}")
        if proposal.rejection_reason:
            typer.echo(f"Rejected: {proposal.rejection_reason}")
    if not proposal.accepted:
        raise typer.Exit(code=1)


@repair_app.command("apply")
def repair_apply(
    repair_id: str = typer.Argument(..., help="Repair bundle ID"),
    attempt: int = typer.Option(..., "--attempt", min=1, help="Attempt number"),
) -> None:
    typer.echo(
        f"Repair {repair_id} attempt {attempt} requires an approved sandbox runner; "
        "no local execution started.",
        err=True,
    )
    raise typer.Exit(code=1)


@validate_app.command("run")
def validate_run(
    artifact_id: str = typer.Argument(..., help="Research artifact ID"),
    artifact_root: str | None = typer.Option(
        None, "--artifact-root", help="Artifact directory override"
    ),
    log_root: str | None = typer.Option(None, "--log-root", help="Log root override"),
    output_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    root = Path(log_root) if log_root else resolve_log_root()
    path = Path(artifact_root) if artifact_root else None
    try:
        report = ClosedLoopService(ClosedLoopStore(root)).validate(
            artifact_id, artifact_root=path
        )
    except (ClosedLoopError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    payload = report.model_dump(mode="json")
    if output_json:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"Validation: {'PASSED' if report.passed else 'FAILED'}")
        for check in report.checks:
            typer.echo(f"  {'✓' if check.passed else '✗'} {check.name}: {check.detail}")
    raise typer.Exit(code=0 if report.passed else 1)
