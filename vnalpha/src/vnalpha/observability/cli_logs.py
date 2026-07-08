"""vnalpha logs command group — inspect, summarize, and bundle run logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

logs_app = typer.Typer(
    name="logs", help="Inspect and bundle file-based observability logs."
)


def _find_log_root() -> Path | None:
    """Resolve the log root from env or defaults."""
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
    """Return the latest run directory using symlink or latest.txt."""
    runs_dir = log_root / "runs"
    if not runs_dir.exists():
        return None
    # Try symlink first
    latest_link = runs_dir / "latest"
    if latest_link.is_symlink():
        target = latest_link.resolve()
        if target.exists():
            return target
    # Try latest.txt
    latest_txt = runs_dir / "latest.txt"
    if latest_txt.exists():
        run_id = latest_txt.read_text(encoding="utf-8").strip()
        candidate = runs_dir / run_id
        if candidate.exists():
            return candidate
    # Fall back: most recently modified directory
    dirs = [d for d in runs_dir.iterdir() if d.is_dir() and d.name != "latest"]
    if dirs:
        return max(dirs, key=lambda d: d.stat().st_mtime)
    return None


@logs_app.command("latest")
def logs_latest() -> None:
    """Print the path to the latest run directory."""
    root = _find_log_root()
    if root is None:
        typer.echo("No log root found. Run any vnalpha command first.", err=True)
        raise typer.Exit(code=1)
    run_dir = _find_latest_run_dir(root)
    if run_dir is None:
        typer.echo("No runs found.", err=True)
        raise typer.Exit(code=1)
    typer.echo(str(run_dir))


@logs_app.command("show")
def logs_show(
    latest: bool = typer.Option(False, "--latest", help="Show latest run logs"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Specific run ID"),
    tail: int = typer.Option(50, "--tail", help="Number of recent events"),
) -> None:
    """Print recent app.jsonl events from a run."""
    run_dir = _resolve_run_dir(latest, run_id)
    app_log = run_dir / "app.jsonl"
    if not app_log.exists():
        typer.echo("No app.jsonl found in run directory.")
        return
    lines = app_log.read_text(encoding="utf-8").splitlines()
    for line in lines[-tail:]:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            ts = str(rec.get("created_at", ""))[:19]
            level = rec.get("level", "INFO")
            event = rec.get("event_type", "")
            summary = rec.get("summary", "")
            typer.echo(f"[{ts}] [{level}] {event}: {summary}")
        except json.JSONDecodeError:
            typer.echo(line)


@logs_app.command("errors")
def logs_errors(
    latest: bool = typer.Option(False, "--latest", help="Show latest run errors"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Specific run ID"),
) -> None:
    """Print errors and warnings from errors.jsonl."""
    run_dir = _resolve_run_dir(latest, run_id)
    errors_log = run_dir / "errors.jsonl"
    if not errors_log.exists():
        typer.echo("No errors.jsonl found.")
        return
    lines = errors_log.read_text(encoding="utf-8").splitlines()
    if not lines:
        typer.echo("No errors recorded.")
        return
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            ts = str(rec.get("created_at", ""))[:19]
            level = rec.get("level", "ERROR")
            etype = rec.get("error_type", "")
            msg = rec.get("error_message", "")
            typer.echo(f"[{ts}] [{level}] {etype}: {msg}")
        except json.JSONDecodeError:
            typer.echo(line)


@logs_app.command("summarize")
def logs_summarize(
    latest: bool = typer.Option(False, "--latest", help="Summarize latest run"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Specific run ID"),
) -> None:
    """Regenerate and print ai-agent-summary.md for a run."""
    run_dir = _resolve_run_dir(latest, run_id)
    from vnalpha.observability.summary import generate_summary

    md = generate_summary(run_dir)
    typer.echo(md)


@logs_app.command("doctor")
def logs_doctor(
    latest: bool = typer.Option(False, "--latest", help="Check latest run"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Specific run ID"),
) -> None:
    """Health check: are logs being written? Any recent errors?"""
    run_dir = _resolve_run_dir(latest, run_id)

    issues: list[str] = []
    ok_files: list[str] = []

    for fname in ["app.jsonl", "audit.jsonl", "errors.jsonl", "environment.json"]:
        fpath = run_dir / fname
        if fpath.exists() and fpath.stat().st_size > 0:
            ok_files.append(fname)
        else:
            issues.append(f"Missing or empty: {fname}")

    errors_log = run_dir / "errors.jsonl"
    error_count = 0
    if errors_log.exists():
        for line in errors_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    if rec.get("level") == "ERROR":
                        error_count += 1
                except json.JSONDecodeError:
                    pass

    typer.echo(f"Run directory: {run_dir}")
    typer.echo(f"Files OK: {', '.join(ok_files) if ok_files else 'none'}")
    if issues:
        typer.echo(f"Issues: {'; '.join(issues)}", err=False)
    typer.echo(f"Error events: {error_count}")
    if issues or error_count > 0:
        typer.echo("Status: DEGRADED")
    else:
        typer.echo("Status: OK")


@logs_app.command("bundle")
def logs_bundle(
    latest: bool = typer.Option(False, "--latest", help="Bundle latest run"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Specific run ID"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path for bundle"
    ),
) -> None:
    """Create a portable tar.gz bundle of run logs for AI agent handoff."""
    run_dir = _resolve_run_dir(latest, run_id)

    # Generate summary before bundling
    from vnalpha.observability.bundle import create_bundle
    from vnalpha.observability.summary import generate_summary

    generate_summary(run_dir)

    out = Path(output) if output else None
    bundle_path = create_bundle(run_dir, output_path=out)
    typer.echo(f"Bundle created: {bundle_path}")


def _resolve_run_dir(use_latest: bool, run_id: Optional[str]) -> Path:
    """Resolve the run directory or exit with error."""
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
