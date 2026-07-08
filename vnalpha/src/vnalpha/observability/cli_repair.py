"""vnalpha repair command group — AI coding repair bundle preparation and tracking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

repair_app = typer.Typer(
    name="repair", help="Prepare and track AI coding repair bundles."
)


def _find_log_root() -> Path | None:
    import os

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


def _find_latest_run_dir(log_root: Path) -> Path | None:
    runs_dir = log_root / "runs"
    if not runs_dir.exists():
        return None
    latest_link = runs_dir / "latest"
    if latest_link.is_symlink():
        target = latest_link.resolve()
        if target.exists():
            return target
    latest_txt = runs_dir / "latest.txt"
    if latest_txt.exists():
        run_id = latest_txt.read_text(encoding="utf-8").strip()
        candidate = runs_dir / run_id
        if candidate.exists():
            return candidate
    dirs = [d for d in runs_dir.iterdir() if d.is_dir() and d.name != "latest"]
    if dirs:
        return max(dirs, key=lambda d: d.stat().st_mtime)
    return None


def _resolve_run_dir(use_latest: bool, run_id: Optional[str]) -> Path:
    root = _find_log_root()
    if root is None:
        typer.echo("No log root found. Run any vnalpha command first.", err=True)
        raise typer.Exit(code=1)
    if run_id:
        run_dir = root / "runs" / run_id
        if not run_dir.exists():
            typer.echo(f"Run directory not found: {run_dir}", err=True)
            raise typer.Exit(code=1)
        return run_dir
    if use_latest:
        run_dir = _find_latest_run_dir(root)
        if run_dir is None:
            typer.echo("No runs found.", err=True)
            raise typer.Exit(code=1)
        return run_dir
    typer.echo("Provide --latest or --run-id.", err=True)
    raise typer.Exit(code=1)


@repair_app.command("prepare")
def repair_prepare(
    latest: bool = typer.Option(False, "--latest", help="Use latest run"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Specific run ID"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Override bundles root directory"
    ),
) -> None:
    """Prepare an AI coding repair bundle from a run's logs.

    Creates bundles/<bundle-id>/ containing:
      ai-coding-prompt.md, reproduction.md, manifest.json,
      ai-agent-summary.md, environment.json, raw-logs/
    """
    run_dir = _resolve_run_dir(latest, run_id)
    root = _find_log_root()

    from vnalpha.observability.repair import (
        create_repair_bundle,
        log_repair_event,
        resolve_bundles_root,
    )

    bundles_root = (
        Path(output) if output else (resolve_bundles_root(root) if root else None)
    )

    try:
        bundle_dir = create_repair_bundle(run_dir, bundles_root=bundles_root)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to create repair bundle: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # Log REPAIR_PREPARED audit event
    log_repair_event(
        "REPAIR_PREPARED",
        f"Repair bundle created: {bundle_dir.name}",
        repair_id=bundle_dir.name,
        extra={"bundle_dir": str(bundle_dir), "source_run_id": run_dir.name},
    )

    typer.echo(f"Repair bundle created: {bundle_dir}")
    typer.echo(f"  ai-coding-prompt.md : {bundle_dir / 'ai-coding-prompt.md'}")
    typer.echo(f"  reproduction.md     : {bundle_dir / 'reproduction.md'}")
    typer.echo(f"  manifest.json       : {bundle_dir / 'manifest.json'}")


@repair_app.command("status")
def repair_status(
    repair_id: str = typer.Argument(..., help="Repair bundle ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show the current status of a repair bundle."""
    root = _find_log_root()
    if root is None:
        typer.echo("No log root found.", err=True)
        raise typer.Exit(code=1)

    from vnalpha.observability.repair import load_repair_state, resolve_bundles_root

    bundles_root = resolve_bundles_root(root)
    bundle_dir = bundles_root / repair_id
    if not bundle_dir.exists():
        typer.echo(f"Bundle not found: {bundle_dir}", err=True)
        raise typer.Exit(code=1)

    state = load_repair_state(bundle_dir)

    # Also read manifest for static info
    manifest_path = bundle_dir / "manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    if output_json:
        merged = {**manifest, **state}
        typer.echo(json.dumps(merged, indent=2, default=str))
        return

    typer.echo(f"Repair bundle: {repair_id}")
    typer.echo(f"  Generated at : {manifest.get('generated_at', 'unknown')}")
    typer.echo(f"  Source runs  : {manifest.get('source_run_ids', [])}")
    typer.echo(f"  Commit SHA   : {manifest.get('source_commit_sha', 'unknown')}")
    typer.echo(f"  Errors       : {manifest.get('error_count', '?')}")
    typer.echo(f"  Failed cmds  : {manifest.get('failed_command_count', '?')}")
    typer.echo("")
    if state:
        typer.echo("Repair tracking:")
        for k, v in state.items():
            typer.echo(f"  {k}: {v}")
    else:
        typer.echo("  No repair tracking data yet.")
        typer.echo(
            "  Update with: vnalpha repair validate <repair-id> "
            "or set fix_branch / pr_number via API."
        )


@repair_app.command("start")
def repair_start(
    repair_id: str = typer.Argument(..., help="Repair bundle ID to start working on"),
    agent: str = typer.Option("", "--agent", help="AI agent or actor starting work"),
) -> None:
    """Log REPAIR_STARTED when an AI coding agent begins work on a bundle.

    Call this at the beginning of a repair session so the start event
    is recorded in repair.jsonl and audit.jsonl.
    """
    from vnalpha.observability.repair import (
        log_repair_event,
        resolve_bundles_root,
        update_repair_state,
    )

    root = _find_log_root()
    bundles_root = resolve_bundles_root(root)
    bundle_dir = bundles_root / repair_id if root else None

    log_repair_event(
        "REPAIR_STARTED",
        f"AI coding agent started repair work on {repair_id}",
        repair_id=repair_id,
        status="STARTED",
        extra={"agent": agent, "repair_id": repair_id},
    )

    if bundle_dir and bundle_dir.exists():
        update_repair_state(bundle_dir, repair_status="STARTED", agent=agent or None)

    typer.echo(f"Repair started: {repair_id}")
    if agent:
        typer.echo(f"  Agent: {agent}")
    typer.echo("REPAIR_STARTED logged.")


@repair_app.command("update")
def repair_update(
    repair_id: str = typer.Argument(..., help="Repair bundle ID to update"),
    fix_branch: Optional[str] = typer.Option(
        None, "--fix-branch", help="Fix branch name"
    ),
    pr_number: Optional[str] = typer.Option(
        None, "--pr-number", help="PR number or URL"
    ),
    commit_sha: Optional[str] = typer.Option(
        None, "--commit-sha", help="Commit SHA(s) involved"
    ),
    outcome: Optional[str] = typer.Option(
        None,
        "--outcome",
        help="Outcome: accepted, rejected, or deferred",
    ),
) -> None:
    """Update repair tracking fields: fix branch, PR, commit SHA, outcome.

    Logs a REPAIR_UPDATED event and persists the fields to repair-state.json.
    Call after creating a fix branch, opening a PR, merging, or making a decision.
    """
    from vnalpha.observability.repair import (
        log_repair_event,
        resolve_bundles_root,
        update_repair_state,
    )

    root = _find_log_root()
    bundles_root = resolve_bundles_root(root)
    bundle_dir = bundles_root / repair_id if root else None

    updates: dict = {}
    if fix_branch is not None:
        updates["fix_branch"] = fix_branch
    if pr_number is not None:
        updates["pr_number"] = pr_number
    if commit_sha is not None:
        updates["commit_sha"] = commit_sha
    if outcome is not None:
        updates["outcome"] = outcome

    if not updates:
        typer.echo(
            "No fields to update. Provide --fix-branch, --pr-number, --commit-sha, or --outcome.",
            err=True,
        )
        raise typer.Exit(code=1)

    log_repair_event(
        "REPAIR_UPDATED",
        f"Repair {repair_id} updated: {', '.join(updates.keys())}",
        repair_id=repair_id,
        status=outcome.upper() if outcome else "UPDATED",
        extra=updates,
    )

    if bundle_dir and bundle_dir.exists():
        update_repair_state(bundle_dir, **updates)

    typer.echo(f"Repair {repair_id} updated:")
    for k, v in updates.items():
        typer.echo(f"  {k}: {v}")


@repair_app.command("validate")
def repair_validate(
    repair_id: str = typer.Argument(..., help="Repair bundle ID"),
    root_override: Optional[str] = typer.Option(
        None, "--log-root", help="Override log root"
    ),
) -> None:
    """Run required validation commands from a repair bundle and record results."""
    log_root = Path(root_override) if root_override else _find_log_root()
    if log_root is None:
        typer.echo("No log root found.", err=True)
        raise typer.Exit(code=1)

    from vnalpha.observability.repair import (
        log_repair_event,
        resolve_bundles_root,
        update_repair_state,
    )

    bundles_root = resolve_bundles_root(log_root)
    bundle_dir = bundles_root / repair_id
    if not bundle_dir.exists():
        typer.echo(f"Bundle not found: {bundle_dir}", err=True)
        raise typer.Exit(code=1)

    # Read test commands from manifest
    manifest_path = bundle_dir / "manifest.json"
    test_commands: list[str] = []
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            test_commands = manifest.get("test_commands", [])
        except Exception:  # noqa: BLE001
            pass

    if not test_commands:
        typer.echo("No test commands found in manifest.", err=True)
        raise typer.Exit(code=1)

    from vnalpha.observability.deploy import run_verify_commands

    typer.echo(f"Running {len(test_commands)} validation command(s)...")
    results = run_verify_commands(test_commands)

    all_passed = all(r["passed"] for r in results)
    validation_status = "PASSED" if all_passed else "FAILED"

    for r in results:
        icon = "✓" if r["passed"] else "✗"
        typer.echo(f"  {icon} [{r['returncode']}] {r['command']}")
        if not r["passed"] and r.get("stderr_tail"):
            typer.echo(f"      stderr: {r['stderr_tail'][:200]}")

    typer.echo(f"\nValidation: {validation_status}")

    # Log validation events
    log_repair_event(
        "REPAIR_VALIDATED",
        f"Validation {validation_status} for {repair_id}",
        repair_id=repair_id,
        status=validation_status,
        extra={
            "validation_status": validation_status,
            "commands_run": len(results),
            "commands_passed": sum(1 for r in results if r["passed"]),
            "validation_commands": test_commands,
        },
    )

    # Persist state
    update_repair_state(
        bundle_dir,
        validation_status=validation_status,
        validation_results=[
            {
                "command": r["command"],
                "passed": r["passed"],
                "returncode": r["returncode"],
            }
            for r in results
        ],
    )

    raise typer.Exit(code=0 if all_passed else 1)
