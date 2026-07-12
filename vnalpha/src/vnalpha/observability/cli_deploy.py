"""vnalpha deploy command group — deploy verification, promotion, and rollback."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer

deploy_app = typer.Typer(
    name="deploy", help="Deploy verification, promotion, and rollback."
)


def _find_log_root() -> Path | None:
    env_override = os.environ.get("VNALPHA_LOG_ROOT", "").strip()
    if env_override:
        root = Path(env_override)
        if root.exists():
            return root
    candidates = [
        Path("/var/log/openstock"),
        Path.home() / ".local" / "state" / "openstock" / "logs",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


@deploy_app.command("verify")
def deploy_verify(
    candidate: str = typer.Argument(..., help="Research artifact candidate to verify"),
    deployment_id: Optional[str] = typer.Option(
        None, "--deployment-id", help="Deployment ID (auto-generated if omitted)"
    ),
    command: Optional[list[str]] = typer.Option(  # noqa: B008
        None,
        "--command",
        "-c",
        help="Verification command (repeatable; uses defaults if omitted)",
    ),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
) -> None:
    from vnalpha.closed_loop.service import ClosedLoopService
    from vnalpha.closed_loop.store import ClosedLoopStore
    from vnalpha.closed_loop.validation import resolve_artifact_root

    log_root = _find_log_root()
    if command:
        typer.echo(
            "Custom deploy commands are not supported for research artifacts.", err=True
        )
        raise typer.Exit(code=1)
    if log_root is None:
        typer.echo("No log root found.", err=True)
        raise typer.Exit(code=1)
    root = (
        Path(candidate)
        if Path(candidate).is_dir()
        else resolve_artifact_root(log_root, candidate)
    )
    result = ClosedLoopService(ClosedLoopStore(log_root)).verify(
        candidate, artifact_root=root, deployment_id=deployment_id
    )

    if output_json:
        typer.echo(result.model_dump_json(indent=2))
    else:
        typer.echo(f"\nVerification: {'PASSED' if result.passed else 'FAILED'}")
        typer.echo(f"Deployment ID: {result.deployment_id}")

    raise typer.Exit(code=0 if result.passed else 1)


@deploy_app.command("promote")
def deploy_promote(
    candidate: str = typer.Argument(..., help="Research artifact candidate to promote"),
    deployment_id: str = typer.Option(
        ..., "--deployment-id", help="Deployment ID from verify step"
    ),
    previous: str = typer.Option(
        "", "--previous", help="Previous version (for rollback reference)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
) -> None:
    from vnalpha.closed_loop.errors import PromotionGateError
    from vnalpha.closed_loop.service import ClosedLoopService
    from vnalpha.closed_loop.store import ClosedLoopStore

    log_root = _find_log_root()

    if log_root is None:
        typer.echo("No log root found.", err=True)
        raise typer.Exit(code=1)
    try:
        state = ClosedLoopService(ClosedLoopStore(log_root)).promote(
            candidate, deployment_id=deployment_id, previous_candidate=previous or None
        )
    except PromotionGateError as exc:
        typer.echo(f"Promotion blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output_json:
        typer.echo(state.model_dump_json(indent=2))
    else:
        typer.echo(f"Promoted research artifact: {candidate}")
        typer.echo(f"Deployment ID: {state.deployment_id}")
        prev = state.previous_candidate or ""
        if prev:
            typer.echo(f"Previous version: {prev}")
            typer.echo(f"Rollback available: vnalpha deploy rollback {deployment_id}")
        else:
            typer.echo(
                "Rollback: available (use vnalpha deploy rollback <deployment-id>)"
            )

    raise typer.Exit(code=0)


@deploy_app.command("rollback")
def deploy_rollback(
    deployment_id: str = typer.Argument(..., help="Deployment ID to roll back"),
    reason: str = typer.Option("", "--reason", help="Reason for rollback"),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
) -> None:
    from vnalpha.closed_loop.service import ClosedLoopService
    from vnalpha.closed_loop.store import ClosedLoopStore

    log_root = _find_log_root()

    if log_root is None:
        typer.echo("No log root found.", err=True)
        raise typer.Exit(code=1)
    try:
        state = ClosedLoopService(ClosedLoopStore(log_root)).rollback(
            deployment_id, reason=reason
        )
    except RuntimeError as exc:
        typer.echo(f"Rollback blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output_json:
        typer.echo(state.model_dump_json(indent=2))
    else:
        typer.echo(f"Rolled back research artifact: {state.candidate}")
        typer.echo(f"Reason: {reason or '(none)'}")
        typer.echo(f"Status: {state.status}")

    raise typer.Exit(code=0)
