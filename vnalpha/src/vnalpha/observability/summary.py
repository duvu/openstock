"""AI-agent summary generator.

Reads all JSONL files in a run directory and writes ai-agent-summary.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    """Parse a JSONL file.  Skips malformed lines silently."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


def generate_summary(run_dir: Path) -> str:
    """Read JSONL files in *run_dir* and write ai-agent-summary.md.

    Returns the generated markdown string.
    """
    audit = _read_jsonl(run_dir / "audit.jsonl")
    _app_logs = _read_jsonl(run_dir / "app.jsonl")
    errors = _read_jsonl(run_dir / "errors.jsonl")
    traces = _read_jsonl(run_dir / "trace.jsonl")
    commands = _read_jsonl(run_dir / "commands.jsonl")

    # --- Run metadata ---
    env_path = run_dir / "environment.json"
    env: dict = {}
    if env_path.exists():
        try:
            env = json.loads(env_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    run_id = env.get("run_id", run_dir.name)
    surface = env.get("surface", "unknown")
    started_at = env.get("started_at", "unknown")
    git_branch = env.get("git_branch", "unknown")
    git_commit = env.get("git_commit", "unknown")
    python_version = env.get("python_version", "unknown")

    # Determine overall result
    error_count = len(errors)
    failed_cmds = [c for c in commands if c.get("status") == "FAILED"]
    result_status = "FAILED" if (error_count > 0 or failed_cmds) else "OK"

    # --- What happened: command list ---
    executed_cmds = [
        c
        for c in commands
        if c.get("event_type")
        in {"COMMAND_STARTED", "COMMAND_SUCCEEDED", "COMMAND_FAILED"}
    ]
    cmd_names: list[str] = list(
        {c.get("command", "") for c in executed_cmds if c.get("command")}
    )

    # Key audit events
    key_audit = [a for a in audit if a.get("event_type") not in {"APP_STARTED"}]

    # --- Suspicious patterns ---
    suspicious: list[str] = []
    # Repeated same error type
    err_types: dict[str, int] = {}
    for e in errors:
        et = e.get("error_type", "")
        if et:
            err_types[et] = err_types.get(et, 0) + 1
    for et, count in err_types.items():
        if count >= 3:
            suspicious.append(f"Error type `{et}` appeared {count} times.")

    # High-latency commands
    slow_cmds = [
        c
        for c in commands
        if isinstance(c.get("duration_ms"), (int, float)) and c["duration_ms"] > 10000
    ]
    for sc in slow_cmds:
        suspicious.append(
            f"Slow command `{sc.get('command', '?')}` took {sc.get('duration_ms')}ms."
        )

    # --- Involved modules ---
    modules: set[str] = set()
    for e in errors:
        if e.get("module"):
            modules.add(e["module"])
    for t in traces:
        if t.get("module"):
            modules.add(t["module"])

    # --- Build markdown ---
    lines: list[str] = [
        "# AI Agent Run Summary",
        "",
        "## Run",
        "",
        f"- **run_id**: `{run_id}`",
        f"- **surface**: {surface}",
        f"- **started_at**: {started_at}",
        f"- **git_branch**: {git_branch}",
        f"- **git_commit**: {git_commit}",
        f"- **python_version**: {python_version}",
        f"- **result**: {result_status}",
        "",
        "## What happened",
        "",
    ]

    if cmd_names:
        lines.append(f"Commands executed: {', '.join(sorted(cmd_names))}")
        lines.append("")
    if key_audit:
        lines.append("Key audit events:")
        for a in key_audit[:20]:
            ts = str(a.get("created_at", ""))[:19]
            lines.append(
                f"  - `{ts}` {a.get('event_type', '')} — {a.get('summary', '')}"
            )
        lines.append("")

    lines += [
        "## Errors",
        "",
    ]
    if errors:
        lines.append(
            "> **Note**: these are observed facts from errors.jsonl."
            " Causes are labeled as *likely* below."
        )
        lines.append("")
        for e in errors[:30]:
            ts = str(e.get("created_at", ""))[:19]
            lines.append(
                f"- `{ts}` [{e.get('level', 'ERROR')}] "
                f"**{e.get('error_type', 'Error')}**: {e.get('error_message', '')}"
            )
            if e.get("likely_cause"):
                lines.append(f"  - *Likely cause*: {e['likely_cause']}")
            if e.get("suggested_next_step"):
                lines.append(f"  - *Suggested*: {e['suggested_next_step']}")
    else:
        lines.append("No errors recorded.")
    lines.append("")

    lines += [
        "## Warnings",
        "",
    ]
    warnings = [e for e in errors if e.get("level") == "WARNING"]
    if warnings:
        for w in warnings[:20]:
            ts = str(w.get("created_at", ""))[:19]
            lines.append(f"- `{ts}` {w.get('error_message', '')}")
    else:
        lines.append("No warnings recorded.")
    lines.append("")

    lines += [
        "## Failed commands",
        "",
    ]
    if failed_cmds:
        for fc in failed_cmds:
            lines.append(
                f"- `{fc.get('command', '?')}` exit={fc.get('exit_code', '?')} "
                f"duration={fc.get('duration_ms', '?')}ms"
            )
            if fc.get("error_message"):
                lines.append(f"  - {fc['error_message']}")
    else:
        lines.append("No failed commands.")
    lines.append("")

    lines += [
        "## Suspicious patterns",
        "",
    ]
    if suspicious:
        for s in suspicious:
            lines.append(f"- {s}")
    else:
        lines.append("No suspicious patterns detected.")
    lines.append("")

    lines += [
        "## Files or modules likely involved",
        "",
        "> *Likely* — inferred from error tracebacks and trace events. Not confirmed.",
        "",
    ]
    if modules:
        for m in sorted(modules):
            lines.append(f"- `{m}`")
    else:
        lines.append("No specific modules identified.")
    lines.append("")

    lines += [
        "## Suggested investigation",
        "",
        "> *Suggested* — not authoritative. Review raw log files for confirmation.",
        "",
    ]
    if errors:
        lines.append("1. Review `errors.jsonl` for full stack traces.")
    if failed_cmds:
        lines.append("2. Check `commands.jsonl` for failed command output tails.")
    if traces:
        lines.append("3. Inspect `trace.jsonl` for timeline reconstruction.")
    if not errors and not failed_cmds:
        lines.append("Run completed without errors. No investigation needed.")
    lines.append("")

    lines += [
        "## Raw logs",
        "",
        "- [`audit.jsonl`](audit.jsonl)",
        "- [`app.jsonl`](app.jsonl)",
        "- [`errors.jsonl`](errors.jsonl)",
        "- [`trace.jsonl`](trace.jsonl)",
        "- [`commands.jsonl`](commands.jsonl)",
        "- [`environment.json`](environment.json)",
        "",
        "---",
        f"*Generated at {datetime.now(timezone.utc).isoformat()}*",
    ]

    md = "\n".join(lines)

    # Write to run_dir
    try:
        (run_dir / "ai-agent-summary.md").write_text(md, encoding="utf-8")
    except OSError:
        pass

    return md
