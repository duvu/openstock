"""Deploy, promote, and rollback event logging and gate enforcement.

Handles:
- deploy event logging to deploy.jsonl / audit.jsonl
- deploy gate enforcement (tests + verification required before promotion)
- rollback logging
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from vnalpha.observability.context import get_correlation_id, get_run_context
from vnalpha.observability.jsonl import append_jsonl
from vnalpha.observability.redaction import redact_dict, redaction_status

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


# ---------------------------------------------------------------------------
# Deploy state store
# ---------------------------------------------------------------------------


def _deploy_state_dir(log_root: Path | None = None) -> Path:
    if log_root is None:
        from vnalpha.observability.context import resolve_log_root

        log_root = resolve_log_root()
    return log_root / "deployments"


def _deploy_state_path(deployment_id: str, log_root: Path | None = None) -> Path:
    return _deploy_state_dir(log_root) / f"{deployment_id}.json"


def load_deploy_state(deployment_id: str, log_root: Path | None = None) -> dict:
    """Load deploy state from deployments/<deployment_id>.json."""
    path = _deploy_state_path(deployment_id, log_root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_deploy_state(
    deployment_id: str, state: dict, log_root: Path | None = None
) -> None:
    """Persist deploy state (best-effort)."""
    try:
        path = _deploy_state_path(deployment_id, log_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def list_deployments(log_root: Path | None = None) -> list[str]:
    """Return list of known deployment IDs."""
    state_dir = _deploy_state_dir(log_root)
    if not state_dir.exists():
        return []
    return [p.stem for p in sorted(state_dir.glob("*.json"))]


# ---------------------------------------------------------------------------
# Deploy event logger
# ---------------------------------------------------------------------------


def log_deploy_event(
    event_type: str,
    summary: str,
    *,
    deployment_id: str = "",
    status: str = "OK",
    run_ctx=None,
    extra: dict | None = None,
    mode: str | None = None,
) -> None:
    """Write a deploy event to audit.jsonl and deploy.jsonl (best-effort)."""
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
            "deployment_id": deployment_id,
            "status": status,
            "summary": summary,
            "redaction_status": redaction_status(mode),
            "metadata": redact_dict(extra or {}, mode),
        }
        # Write to audit.jsonl
        append_jsonl(ctx.audit_path, record)
        # Write to dedicated deploy.jsonl
        deploy_path = ctx.run_dir / "deploy.jsonl"
        append_jsonl(deploy_path, record)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Deploy verification gate
# ---------------------------------------------------------------------------


class DeployGateError(Exception):
    """Raised when deploy promotion is blocked by a gate failure."""


def run_verify_commands(
    commands: list[str],
    *,
    cwd: str | None = None,
    timeout: int = 300,
) -> list[dict]:
    """Run each command and return results.

    Returns list of dicts with keys: command, returncode, stdout_tail,
    stderr_tail, passed.
    """
    results: list[dict] = []
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                shell=True,  # noqa: S602
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            stdout_tail = proc.stdout[-2000:] if proc.stdout else ""
            stderr_tail = proc.stderr[-2000:] if proc.stderr else ""
            results.append(
                {
                    "command": cmd,
                    "returncode": proc.returncode,
                    "stdout_tail": stdout_tail,
                    "stderr_tail": stderr_tail,
                    "passed": proc.returncode == 0,
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "command": cmd,
                    "returncode": -1,
                    "stdout_tail": "",
                    "stderr_tail": f"TIMEOUT after {timeout}s",
                    "passed": False,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "command": cmd,
                    "returncode": -1,
                    "stdout_tail": "",
                    "stderr_tail": str(exc),
                    "passed": False,
                }
            )
    return results


def verify_deploy_candidate(
    candidate_version: str,
    *,
    verify_commands: list[str] | None = None,
    deployment_id: str | None = None,
    log_root: Path | None = None,
    run_ctx=None,
) -> dict:
    """Run deploy verification and return a result dict.

    Returns {deployment_id, candidate_version, verification_status,
             command_results, passed}.
    """
    if verify_commands is None:
        verify_commands = [
            "cd vnalpha && make test-vnalpha",
            "cd vnalpha && make lint-vnalpha",
        ]

    if deployment_id is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        short = uuid4().hex[:8]
        deployment_id = f"deploy_{ts}_{short}"

    log_deploy_event(
        "DEPLOY_VERIFY_STARTED",
        f"Verifying candidate {candidate_version}",
        deployment_id=deployment_id,
        run_ctx=run_ctx,
        extra={"candidate_version": candidate_version},
    )

    command_results = run_verify_commands(verify_commands)
    all_passed = all(r["passed"] for r in command_results)
    verification_status = "PASSED" if all_passed else "FAILED"

    state: dict = {
        "deployment_id": deployment_id,
        "candidate_version": candidate_version,
        "previous_version": "",
        "verification_status": verification_status,
        "command_results": command_results,
        "deploy_status": "PENDING",
        "rollback_status": "NOT_REQUIRED",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    save_deploy_state(deployment_id, state, log_root)

    log_deploy_event(
        "DEPLOY_VERIFY_COMPLETED",
        f"Verification {verification_status} for {candidate_version}",
        deployment_id=deployment_id,
        status=verification_status,
        run_ctx=run_ctx,
        extra={
            "candidate_version": candidate_version,
            "passed": all_passed,
            "failed_commands": [
                r["command"] for r in command_results if not r["passed"]
            ],
        },
    )

    return {
        "deployment_id": deployment_id,
        "candidate_version": candidate_version,
        "verification_status": verification_status,
        "command_results": command_results,
        "passed": all_passed,
    }


def promote_candidate(
    candidate: str,
    *,
    deployment_id: str,
    previous_version: str = "",
    force: bool = False,
    log_root: Path | None = None,
    run_ctx=None,
) -> dict:
    """Promote a candidate version.

    Blocks if verification has not passed, unless force=True.
    Returns updated deploy state.
    """
    state = load_deploy_state(deployment_id, log_root)

    if not state:
        raise DeployGateError(
            f"No deploy state found for {deployment_id}. Run verify first."
        )

    verification_status = state.get("verification_status", "UNKNOWN")
    if verification_status != "PASSED" and not force:
        log_deploy_event(
            "DEPLOY_PROMOTION_BLOCKED",
            f"Promotion blocked: verification={verification_status}",
            deployment_id=deployment_id,
            status="BLOCKED",
            run_ctx=run_ctx,
            extra={
                "candidate": candidate,
                "reason": f"verification_status={verification_status}",
            },
        )
        raise DeployGateError(
            f"Cannot promote: verification_status={verification_status}. "
            "Fix failures or use force=True to override (not recommended)."
        )

    state["previous_version"] = previous_version
    state["candidate_version"] = candidate
    state["deploy_status"] = "PROMOTED"
    state["promoted_at"] = _now_iso()
    state["updated_at"] = _now_iso()
    save_deploy_state(deployment_id, state, log_root)

    log_deploy_event(
        "DEPLOY_PROMOTED",
        f"Promoted {candidate} (previous={previous_version})",
        deployment_id=deployment_id,
        status="PROMOTED",
        run_ctx=run_ctx,
        extra={
            "candidate_version": candidate,
            "previous_version": previous_version,
            "forced": force,
        },
    )

    return state


def rollback_deployment(
    deployment_id: str,
    *,
    reason: str = "",
    log_root: Path | None = None,
    run_ctx=None,
) -> dict:
    """Record a rollback for a deployment.

    Returns updated deploy state.
    """
    state = load_deploy_state(deployment_id, log_root)

    previous = state.get("previous_version", "unknown")

    log_deploy_event(
        "DEPLOY_ROLLBACK_STARTED",
        f"Rolling back {deployment_id} to {previous}",
        deployment_id=deployment_id,
        status="ROLLING_BACK",
        run_ctx=run_ctx,
        extra={"previous_version": previous, "reason": reason},
    )

    state["rollback_status"] = "ROLLED_BACK"
    state["rollback_at"] = _now_iso()
    state["rollback_reason"] = reason
    state["updated_at"] = _now_iso()
    save_deploy_state(deployment_id, state, log_root)

    log_deploy_event(
        "DEPLOY_ROLLED_BACK",
        f"Rolled back to {previous}",
        deployment_id=deployment_id,
        status="ROLLED_BACK",
        run_ctx=run_ctx,
        extra={"previous_version": previous, "reason": reason},
    )

    return state


def record_post_deploy_smoke(
    deployment_id: str,
    *,
    smoke_passed: bool,
    details: str = "",
    log_root: Path | None = None,
    run_ctx=None,
) -> dict:
    """Record post-deploy smoke test result."""
    status = "PASSED" if smoke_passed else "FAILED"
    state = load_deploy_state(deployment_id, log_root)
    state["smoke_status"] = status
    state["smoke_details"] = details
    state["updated_at"] = _now_iso()
    save_deploy_state(deployment_id, state, log_root)

    log_deploy_event(
        "DEPLOY_SMOKE_COMPLETED",
        f"Post-deploy smoke {status}: {details}",
        deployment_id=deployment_id,
        status=status,
        run_ctx=run_ctx,
        extra={"smoke_passed": smoke_passed, "details": details},
    )

    return state
