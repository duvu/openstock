"""Repair bundle preparation and execution tracking.

Handles:
- repair bundle creation (ai-coding-prompt.md, reproduction.md, manifest.json)
- repair audit event logging to repair.jsonl / audit.jsonl
- repair state persistence under bundles/<bundle-id>/

Governance (task 0.6):
  AI-assisted repair MUST NOT bypass any of the following gates. These are
  enforced at the CLI and function level; callers must not override silently.

  - Unit/integration tests: every candidate fix runs `make test-vnalpha` or
    equivalent before acceptance.
  - Code review: changes are submitted as a pull request and reviewed by a
    human or a second automated check before merge.
  - Deploy verification: `vnalpha deploy verify` must pass (PASSED status) before
    `vnalpha deploy promote` is invoked.
  - Rollback availability: a rollback path must exist and be logged before any
    promotion is finalized.

  Any attempt to set `force=True` on `promote_candidate` without PASSED
  verification must be logged as a DEPLOY_GATE_OVERRIDE event and requires
  explicit operator acknowledgement.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from vnalpha.observability.context import get_correlation_id, get_run_context
from vnalpha.observability.jsonl import append_jsonl
from vnalpha.observability.redaction import redact_dict, redact_str, redaction_status
from vnalpha.observability.summary import _read_jsonl

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GUARDRAILS = """\
## Required guardrails

**DO NOT** add, modify, or enable any of:
- Broker connectivity or order execution
- Account, holdings, or position management features
- Trading signal execution or live-order routing
- Any feature that interacts with live financial market APIs beyond read-only data

All changes must remain in data/analysis/observability scope only.
"""

# Files excluded from repair bundles (same policy as log bundles)
_EXCLUDED_PATTERNS: tuple[str, ...] = (
    "*.key", "*.pem", "*.p12", "*.pfx", "*.env", ".env*",
    "*.credentials", "secrets*", "*.password",
)


def _is_safe(path: Path) -> bool:
    name = path.name
    for pat in _EXCLUDED_PATTERNS:
        if pat.startswith("*"):
            if name.endswith(pat[1:]):
                return False
        elif pat.endswith("*"):
            if name.startswith(pat[:-1]):
                return False
        elif name == pat:
            return False
    return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Repair bundle directory resolution
# ---------------------------------------------------------------------------

def resolve_bundles_root(log_root: Path | None = None) -> Path:
    """Return the bundles/ directory under the log root."""
    if log_root is None:
        from vnalpha.observability.context import resolve_log_root
        log_root = resolve_log_root()
    return log_root / "bundles"


# ---------------------------------------------------------------------------
# Bundle content generators
# ---------------------------------------------------------------------------

def _collect_git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .decode()
            .strip()
        )
    except Exception:  # noqa: BLE001
        return "unknown"


def _generate_ai_coding_prompt(
    run_dir: Path,
    errors: list[dict],
    failed_cmds: list[dict],
    suspicious: list[str],
    modules: list[str],
    env: dict,
    test_commands: list[str],
    mode: str | None = None,
) -> str:
    """Generate ai-coding-prompt.md content."""
    run_id = env.get("run_id", run_dir.name)
    branch = env.get("git_branch", "unknown")
    commit = env.get("git_commit", "unknown")

    lines: list[str] = [
        "# AI Coding Repair Prompt",
        "",
        "## Objective",
        "",
        "Investigate and fix the failure described below.",
        "Propose the minimal code change that resolves the root cause.",
        "",
        "## Source runs and commit",
        "",
        f"- **run_id**: `{run_id}`",
        f"- **git_branch**: {branch}",
        f"- **git_commit**: {commit}",
        "",
        "## Observed failure",
        "",
    ]

    if errors:
        lines.append("Errors from `errors.jsonl`:")
        lines.append("")
        for e in errors[:10]:
            etype = e.get("error_type", "Error")
            emsg = redact_str(e.get("error_message", ""), mode)
            ts = str(e.get("created_at", ""))[:19]
            lines.append(f"- `{ts}` **{etype}**: {emsg}")
            if e.get("likely_cause"):
                lines.append(f"  - *Likely cause*: {e['likely_cause']}")
    else:
        lines.append("No explicit error events captured.")
    lines.append("")

    lines += [
        "## Reproduction steps",
        "",
    ]
    if failed_cmds:
        lines.append("Failed commands (from `commands.jsonl`):")
        lines.append("")
        for fc in failed_cmds[:10]:
            cmd = fc.get("command", "?")
            args = fc.get("args", "")
            exit_code = fc.get("exit_code", "?")
            lines.append("```")
            lines.append(f"{cmd} {args}".strip())
            lines.append(f"# exit_code={exit_code}")
            if fc.get("stderr_tail"):
                lines.append(f"# stderr: {redact_str(str(fc['stderr_tail']), mode)[:200]}")
            lines.append("```")
            lines.append("")
    else:
        lines.append("No failed commands recorded.")
        lines.append("")

    lines += [
        "## Relevant log excerpts",
        "",
        "See `raw-logs/` in this bundle for full JSONL files.",
        "",
    ]

    if suspicious:
        lines += ["## Suspicious patterns", ""]
        for s in suspicious:
            lines.append(f"- {s}")
        lines.append("")

    lines += ["## Likely files/modules to inspect", ""]
    if modules:
        for m in modules[:20]:
            lines.append(f"- `{m}`")
    else:
        lines.append("*(not determined — review stack traces in errors.jsonl)*")
    lines.append("")

    lines += [_GUARDRAILS, ""]

    lines += [
        "## Required validation commands",
        "",
        "Run ALL of the following before marking fix complete:",
        "",
    ]
    for tc in test_commands:
        lines.append(f"```bash\n{tc}\n```")
        lines.append("")

    lines += [
        "## Expected output",
        "",
        "- **proposed fix summary**: brief description of change",
        "- **changed files**: list of files modified",
        "- **commands run**: all validation commands executed",
        "- **validation result**: PASS / FAIL per command",
        "- **risks/deferred items**: any known limitations or deferrals",
    ]

    return "\n".join(lines)


def _generate_reproduction_md(
    run_dir: Path,
    failed_cmds: list[dict],
    errors: list[dict],
    env: dict,
    mode: str | None = None,
) -> str:
    """Generate reproduction.md content."""
    run_id = env.get("run_id", run_dir.name)
    lines: list[str] = [
        "# Reproduction",
        "",
        f"**run_id**: `{run_id}`",
        f"**git_branch**: {env.get('git_branch', 'unknown')}",
        f"**git_commit**: {env.get('git_commit', 'unknown')}",
        "",
        "## Failing commands",
        "",
    ]
    if failed_cmds:
        for fc in failed_cmds:
            cmd = fc.get("command", "?")
            args = fc.get("args", "")
            lines.append(f"### `{cmd}`")
            lines.append("")
            lines.append(f"```bash\n{cmd} {args}\n```".strip())
            lines.append("")
            lines.append(f"**Exit code**: `{fc.get('exit_code', '?')}`")
            lines.append(f"**Duration**: {fc.get('duration_ms', '?')}ms")
            if fc.get("stderr_tail"):
                lines.append("")
                lines.append("**stderr (tail)**:")
                lines.append(
                    f"```\n{redact_str(str(fc['stderr_tail']), mode)[:500]}\n```"
                )
            lines.append("")
    else:
        lines.append("No failed commands recorded.")
        lines.append("")

    lines += ["## Expected behavior", ""]
    lines.append("*(describe the expected outcome here — fill in before sharing)*")
    lines.append("")

    lines += ["## Actual behavior", ""]
    if errors:
        lines.append("Errors observed:")
        for e in errors[:5]:
            etype = e.get("error_type", "")
            emsg = redact_str(e.get("error_message", ""), mode)
            lines.append(f"- **{etype}**: {emsg}")
    else:
        lines.append("*(fill in actual observed behavior)*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main repair bundle creator
# ---------------------------------------------------------------------------

def create_repair_bundle(
    run_dir: Path,
    bundles_root: Path | None = None,
    *,
    test_commands: list[str] | None = None,
    mode: str | None = None,
) -> Path:
    """Create a repair bundle under bundles/<bundle-id>/.

    Returns the path to the created bundle directory.

    Generates:
    - ai-coding-prompt.md
    - reproduction.md
    - manifest.json
    - environment.json (copy)
    - raw-logs/ with JSONL files
    """
    if bundles_root is None:
        bundles_root = resolve_bundles_root()

    if test_commands is None:
        test_commands = [
            "cd vnalpha && make test-vnalpha",
            "cd vnalpha && make lint-vnalpha",
        ]

    # Generate bundle ID
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    short = _short_id()
    bundle_id = f"repair_{ts}_{short}"
    bundle_dir = bundles_root / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    raw_logs_dir = bundle_dir / "raw-logs"
    raw_logs_dir.mkdir(parents=True, exist_ok=True)

    # Read JSONL data for analysis
    errors = _read_jsonl(run_dir / "errors.jsonl")
    commands = _read_jsonl(run_dir / "commands.jsonl")
    traces = _read_jsonl(run_dir / "trace.jsonl")
    _read_jsonl(run_dir / "audit.jsonl")  # read for side-effects / future use

    failed_cmds = [c for c in commands if c.get("status") == "FAILED"]

    # Suspicious patterns
    suspicious: list[str] = []
    err_types: dict[str, int] = {}
    for e in errors:
        et = e.get("error_type", "")
        if et:
            err_types[et] = err_types.get(et, 0) + 1
    for et, count in err_types.items():
        if count >= 2:
            suspicious.append(f"Error type `{et}` repeated {count} times.")
    slow_cmds = [
        c for c in commands
        if isinstance(c.get("duration_ms"), (int, float)) and c["duration_ms"] > 10000
    ]
    for sc in slow_cmds:
        suspicious.append(
            f"Slow command `{sc.get('command', '?')}` took {sc.get('duration_ms')}ms."
        )

    # Involved modules
    modules: list[str] = list({
        e.get("module", "")
        for e in errors
        if e.get("module")
    } | {
        t.get("module", "")
        for t in traces
        if t.get("module")
    })

    # Environment
    env_path = run_dir / "environment.json"
    env: dict = {}
    if env_path.exists():
        try:
            env = json.loads(env_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    commit = _collect_git_commit()
    source_run_ids = [env.get("run_id", run_dir.name)]

    # Copy JSONL files (safe only)
    for fname in ["audit.jsonl", "errors.jsonl", "trace.jsonl", "commands.jsonl"]:
        src = run_dir / fname
        if src.exists() and _is_safe(src):
            import shutil
            shutil.copy2(src, raw_logs_dir / fname)

    # Copy environment.json
    if env_path.exists() and _is_safe(env_path):
        import shutil
        shutil.copy2(env_path, bundle_dir / "environment.json")

    # Copy or regenerate ai-agent-summary.md
    summary_src = run_dir / "ai-agent-summary.md"
    if summary_src.exists():
        import shutil
        shutil.copy2(summary_src, bundle_dir / "ai-agent-summary.md")
    else:
        from vnalpha.observability.summary import generate_summary
        md = generate_summary(run_dir)
        (bundle_dir / "ai-agent-summary.md").write_text(md, encoding="utf-8")

    # Generate ai-coding-prompt.md
    prompt_md = _generate_ai_coding_prompt(
        run_dir=run_dir,
        errors=errors,
        failed_cmds=failed_cmds,
        suspicious=suspicious,
        modules=modules,
        env=env,
        test_commands=test_commands,
        mode=mode,
    )
    (bundle_dir / "ai-coding-prompt.md").write_text(prompt_md, encoding="utf-8")

    # Generate reproduction.md
    repro_md = _generate_reproduction_md(
        run_dir=run_dir,
        failed_cmds=failed_cmds,
        errors=errors,
        env=env,
        mode=mode,
    )
    (bundle_dir / "reproduction.md").write_text(repro_md, encoding="utf-8")

    # Generate manifest.json
    manifest = {
        "bundle_id": bundle_id,
        "bundle_type": "repair",
        "generated_at": _now_iso(),
        "source_run_ids": source_run_ids,
        "source_commit_sha": commit,
        "redaction_mode": mode or "redacted",
        "included_files": [
            "ai-coding-prompt.md",
            "ai-agent-summary.md",
            "reproduction.md",
            "manifest.json",
            "environment.json",
        ]
        + [
            f"raw-logs/{fname}"
            for fname in ["audit.jsonl", "errors.jsonl", "trace.jsonl", "commands.jsonl"]
            if (raw_logs_dir / fname).exists()
        ],
        "error_count": len(errors),
        "warning_count": len([e for e in errors if e.get("level") == "WARNING"]),
        "failed_command_count": len(failed_cmds),
        "top_errors": [
            {
                "error_type": e.get("error_type", ""),
                "error_message": redact_str(e.get("error_message", ""), mode)[:200],
            }
            for e in errors[:5]
        ],
        "suspicious_patterns": suspicious,
        "likely_modules": modules[:20],
        "test_commands": test_commands,
        "guardrails": (
            "No broker/order/account/holdings/trading execution features. "
            "Data/analysis/observability scope only."
        ),
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    return bundle_dir


# ---------------------------------------------------------------------------
# Repair event logger
# ---------------------------------------------------------------------------

def log_repair_event(
    event_type: str,
    summary: str,
    *,
    repair_id: str = "",
    status: str = "OK",
    run_ctx=None,
    extra: dict | None = None,
    mode: str | None = None,
) -> None:
    """Write a repair event to audit.jsonl and repair.jsonl (best-effort)."""
    try:
        ctx = run_ctx or get_run_context()
        if ctx is None:
            return
        record: dict = {
            "event_id": uuid4().hex,
            "run_id": ctx.run_id,
            "created_at": _now_iso(),
            "level": "INFO",
            "event_type": event_type,
            "surface": ctx.surface,
            "correlation_id": get_correlation_id(),
            "repair_id": repair_id,
            "status": status,
            "summary": summary,
            "redaction_status": redaction_status(mode),
            "metadata": redact_dict(extra or {}, mode),
        }
        # Write to audit.jsonl
        append_jsonl(ctx.audit_path, record)
        # Write to dedicated repair.jsonl
        repair_path = ctx.run_dir / "repair.jsonl"
        append_jsonl(repair_path, record)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Repair state store
# ---------------------------------------------------------------------------

def _repair_state_path(bundle_dir: Path) -> Path:
    return bundle_dir / "repair-state.json"


def load_repair_state(bundle_dir: Path) -> dict:
    """Load repair state from bundle_dir/repair-state.json."""
    state_path = _repair_state_path(bundle_dir)
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_repair_state(bundle_dir: Path, state: dict) -> None:
    """Persist repair state to bundle_dir/repair-state.json (best-effort)."""
    try:
        state_path = _repair_state_path(bundle_dir)
        state_path.write_text(
            json.dumps(state, indent=2, default=str), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001
        pass


def update_repair_state(bundle_dir: Path, **kwargs) -> dict:
    """Update and persist repair state fields."""
    state = load_repair_state(bundle_dir)
    state.update(kwargs)
    state["updated_at"] = _now_iso()
    save_repair_state(bundle_dir, state)
    return state
