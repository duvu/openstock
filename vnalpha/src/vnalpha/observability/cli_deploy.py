"""vnalpha deploy command group — deploy verification, promotion, and rollback."""

from __future__ import annotations

import json
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
    candidate: str = typer.Argument(..., help="Candidate version string to verify"),
    deployment_id: Optional[str] = typer.Option(
        None, "--deployment-id", help="Deployment ID (auto-generated if omitted)"
    ),
    command: Optional[list[str]] = typer.Option(  # noqa: B008
        None, "--command", "-c", help="Verification command (repeatable; uses defaults if omitted)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
) -> None:
    """Run verification gates for a deploy candidate.

    Runs test and lint commands. Records DEPLOY_VERIFY_STARTED and
    DEPLOY_VERIFY_COMPLETED events in deploy.jsonl and audit.jsonl.
    """
    from vnalpha.observability.deploy import verify_deploy_candidate

    log_root = _find_log_root()
    verify_commands = list(command) if command else None

    typer.echo(f"Verifying candidate: {candidate}")
    if verify_commands:
        typer.echo(f"Commands: {verify_commands}")

    result = verify_deploy_candidate(
        candidate,
        verify_commands=verify_commands,
        deployment_id=deployment_id,
        log_root=log_root,
    )

    if output_json:
        # Omit full command output to keep JSON clean
        out = {k: v for k, v in result.items() if k != "command_results"}
        out["failed_commands"] = [
            r["command"] for r in result.get("command_results", []) if not r["passed"]
        ]
        typer.echo(json.dumps(out, indent=2))
    else:
        for r in result.get("command_results", []):
            icon = "✓" if r["passed"] else "✗"
            typer.echo(f"  {icon} [{r['returncode']}] {r['command']}")
            if not r["passed"] and r.get("stderr_tail"):
                typer.echo(f"      stderr: {r['stderr_tail'][:200]}")

        status = result["verification_status"]
        typer.echo(f"\nVerification: {status}")
        typer.echo(f"Deployment ID: {result['deployment_id']}")

    raise typer.Exit(code=0 if result["passed"] else 1)


@deploy_app.command("promote")
def deploy_promote(
    candidate: str = typer.Argument(..., help="Candidate version to promote"),
    deployment_id: str = typer.Option(
        ..., "--deployment-id", help="Deployment ID from verify step"
    ),
    previous: str = typer.Option("", "--previous", help="Previous version (for rollback reference)"),
    force: bool = typer.Option(
        False, "--force", help="Promote even if verification did not pass (not recommended)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
) -> None:
    """Promote a candidate version.

    Blocked if verification has not passed (unless --force is used).
    Records DEPLOY_PROMOTED or DEPLOY_PROMOTION_BLOCKED events.

    Log rollback availability: the previous version is stored in deployment
    state so rollback can reference it via `vnalpha deploy rollback`.
    """
    from vnalpha.observability.deploy import DeployGateError, promote_candidate

    log_root = _find_log_root()

    try:
        state = promote_candidate(
            candidate,
            deployment_id=deployment_id,
            previous_version=previous,
            force=force,
            log_root=log_root,
        )
    except DeployGateError as exc:
        typer.echo(f"Promotion blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output_json:
        typer.echo(json.dumps(state, indent=2, default=str))
    else:
        typer.echo(f"Promoted: {candidate}")
        typer.echo(f"Deployment ID: {deployment_id}")
        prev = state.get("previous_version", "")
        if prev:
            typer.echo(f"Previous version: {prev}")
            typer.echo(
                f"Rollback available: vnalpha deploy rollback {deployment_id}"
            )
        else:
            typer.echo("Rollback: available (use vnalpha deploy rollback <deployment-id>)")

    raise typer.Exit(code=0)


@deploy_app.command("rollback")
def deploy_rollback(
    deployment_id: str = typer.Argument(..., help="Deployment ID to roll back"),
    reason: str = typer.Option("", "--reason", help="Reason for rollback"),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
) -> None:
    """Roll back a deployment.

    Records DEPLOY_ROLLBACK_STARTED and DEPLOY_ROLLED_BACK events.
    """
    from vnalpha.observability.deploy import rollback_deployment

    log_root = _find_log_root()

    state = rollback_deployment(deployment_id, reason=reason, log_root=log_root)

    if output_json:
        typer.echo(json.dumps(state, indent=2, default=str))
    else:
        typer.echo(f"Rolled back deployment: {deployment_id}")
        prev = state.get("previous_version", "")
        if prev:
            typer.echo(f"Reverted to: {prev}")
        typer.echo(f"Reason: {reason or '(none)'}")
        typer.echo(f"Status: {state.get('rollback_status', 'ROLLED_BACK')}")

    raise typer.Exit(code=0)


@deploy_app.command("smoke")
def deploy_smoke(
    deployment_id: str = typer.Argument(..., help="Deployment ID to record smoke result for"),
    passed: bool = typer.Option(
        ..., "--passed/--failed", help="Whether the smoke test passed"
    ),
    details: str = typer.Option("", "--details", help="Additional smoke test details"),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
) -> None:
    """Record post-deploy smoke test result.

    Records DEPLOY_SMOKE_COMPLETED event.
    """
    from vnalpha.observability.deploy import record_post_deploy_smoke

    log_root = _find_log_root()

    state = record_post_deploy_smoke(
        deployment_id,
        smoke_passed=passed,
        details=details,
        log_root=log_root,
    )

    if output_json:
        typer.echo(json.dumps(state, indent=2, default=str))
    else:
        status = "PASSED" if passed else "FAILED"
        typer.echo(f"Smoke: {status}")
        typer.echo(f"Deployment ID: {deployment_id}")
        if details:
            typer.echo(f"Details: {details}")

    raise typer.Exit(code=0 if passed else 1)


@deploy_app.command("status")
def deploy_status(
    deployment_id: str = typer.Argument(..., help="Deployment ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show current state of a deployment."""
    from vnalpha.observability.deploy import load_deploy_state

    log_root = _find_log_root()
    state = load_deploy_state(deployment_id, log_root)

    if not state:
        typer.echo(f"No state found for deployment: {deployment_id}", err=True)
        raise typer.Exit(code=1)

    if output_json:
        typer.echo(json.dumps(state, indent=2, default=str))
    else:
        typer.echo(f"Deployment: {deployment_id}")
        typer.echo(f"  Candidate  : {state.get('candidate_version', '?')}")
        typer.echo(f"  Previous   : {state.get('previous_version', '?')}")
        typer.echo(f"  Verified   : {state.get('verification_status', '?')}")
        typer.echo(f"  Deploy     : {state.get('deploy_status', '?')}")
        typer.echo(f"  Rollback   : {state.get('rollback_status', '?')}")
        typer.echo(f"  Smoke      : {state.get('smoke_status', 'NOT_RUN')}")
        typer.echo(f"  Created    : {state.get('created_at', '?')}")
        typer.echo(f"  Updated    : {state.get('updated_at', '?')}")

    raise typer.Exit(code=0)


@deploy_app.command("list")
def deploy_list(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List known deployment IDs."""
    from vnalpha.observability.deploy import list_deployments

    log_root = _find_log_root()
    deployments = list_deployments(log_root)

    if output_json:
        typer.echo(json.dumps(deployments))
    else:
        if not deployments:
            typer.echo("No deployments found.")
        else:
            typer.echo(f"Deployments ({len(deployments)}):")
            for d in deployments:
                typer.echo(f"  {d}")

    raise typer.Exit(code=0)
