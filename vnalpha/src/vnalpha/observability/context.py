"""RunContext and correlation ID management for file-based observability.

RunContext: top-level process / session identifier.
CorrelationContext: workflow identifier inside a run.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# ---------------------------------------------------------------------------
# ContextVar for correlation ID — async-safe, inherits across tasks
# ---------------------------------------------------------------------------

_CORRELATION_ID: ContextVar[str] = ContextVar("_obs_correlation_id", default="unset")


def set_correlation_id(parent: str | None = None) -> str:
    cid = parent if parent not in {None, ""} else uuid4().hex
    _CORRELATION_ID.set(cid)
    return cid


def get_correlation_id() -> str:
    """Return current correlation ID or 'unset'."""
    return _CORRELATION_ID.get()


def new_span_id() -> str:
    """Generate a short span ID for a child step."""
    return uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Log root resolution
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM_ROOT = Path("/var/log/openstock")
_DEFAULT_LOCAL_ROOT = Path.home() / ".local" / "state" / "openstock" / "logs"


def resolve_log_root() -> Path:
    """Resolve the log root directory.

    Priority:
    1. VNALPHA_LOG_ROOT env var
    2. /var/log/openstock (if writable)
    3. ~/.local/state/openstock/logs (fallback)
    """
    env_override = os.environ.get("VNALPHA_LOG_ROOT", "").strip()
    if env_override:
        return Path(env_override)
    try:
        _DEFAULT_SYSTEM_ROOT.mkdir(parents=True, exist_ok=True)
        test_file = _DEFAULT_SYSTEM_ROOT / ".write_test"
        test_file.touch()
        test_file.unlink()
        return _DEFAULT_SYSTEM_ROOT
    except (OSError, PermissionError):
        return _DEFAULT_LOCAL_ROOT


# ---------------------------------------------------------------------------
# RunContext
# ---------------------------------------------------------------------------


@dataclass
class RunContext:
    """Top-level run / session context.

    Created once per process entry point (CLI command, TUI session, pipeline).
    """

    run_id: str
    surface: str  # cli | tui | pipeline | verify | backup
    actor: str
    log_root: Path
    run_dir: Path = field(init=False)
    started_at: str = field(init=False)

    def __post_init__(self) -> None:
        self.run_dir = self.log_root / "runs" / self.run_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._init_run_dir()

    def _init_run_dir(self) -> None:
        """Create the run directory and write initial files."""
        try:
            runs_root = self.log_root / "runs"
            self.log_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.log_root.is_symlink():
                raise OSError("log root must not be a symlink")
            self.log_root.chmod(0o700)
            runs_root.mkdir(exist_ok=True, mode=0o700)
            if runs_root.is_symlink():
                raise OSError("runs root must not be a symlink")
            runs_root.chmod(0o700)
            self.run_dir.mkdir(exist_ok=False, mode=0o700)
            self.run_dir.chmod(0o700)
            self._write_latest_pointer()
            self._write_environment_json()
            self._write_readme()
        except Exception as exc:  # noqa: BLE001
            import sys

            sys.stderr.write(f"[observability] RunContext init failed: {exc}\n")

    def _write_latest_pointer(self) -> None:
        latest_link = self.log_root / "runs" / "latest"
        latest_txt = self.log_root / "runs" / "latest.txt"
        try:
            if latest_link.is_symlink():
                latest_link.unlink()
            latest_link.symlink_to(self.run_dir)
        except (OSError, NotImplementedError):
            try:
                _secure_write_text(latest_txt, self.run_id + "\n")
            except OSError:
                pass

    def _write_environment_json(self) -> None:
        env: dict = {
            "run_id": self.run_id,
            "surface": self.surface,
            "actor": self.actor,
            "started_at": self.started_at,
            "python_version": sys.version,
            "platform": platform.platform(),
            "log_root": str(self.log_root),
        }
        env.update(_collect_git_info())
        try:
            _secure_write_text(
                self.run_dir / "environment.json",
                json.dumps(env, indent=2, default=str),
            )
        except OSError:
            pass

    def _write_readme(self) -> None:
        readme = _RUN_README_TEMPLATE.format(
            run_id=self.run_id,
            surface=self.surface,
            started_at=self.started_at,
        )
        try:
            _secure_write_text(self.run_dir / "README.md", readme)
        except OSError:
            pass

    # Convenience paths
    @property
    def audit_path(self) -> Path:
        return self.run_dir / "audit.jsonl"

    @property
    def app_path(self) -> Path:
        return self.run_dir / "app.jsonl"

    @property
    def errors_path(self) -> Path:
        return self.run_dir / "errors.jsonl"

    @property
    def trace_path(self) -> Path:
        return self.run_dir / "trace.jsonl"

    @property
    def commands_path(self) -> Path:
        return self.run_dir / "commands.jsonl"


def _secure_write_text(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as handle:
            handle.write(content)
    finally:
        os.close(descriptor)


def make_run_context(
    surface: str,
    actor: str = "cli",
    log_root: Path | None = None,
) -> RunContext:
    """Create a RunContext with auto-generated run_id."""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    short_id = uuid4().hex[:8]
    run_id = f"{surface}_{ts}_{short_id}"
    resolved_root = log_root or resolve_log_root()
    return RunContext(
        run_id=run_id,
        surface=surface,
        actor=actor,
        log_root=resolved_root,
    )


# ---------------------------------------------------------------------------
# CorrelationContext
# ---------------------------------------------------------------------------


@dataclass
class CorrelationContext:
    """Workflow identifier inside a run."""

    correlation_id: str
    parent_span_id: str | None = None


def make_correlation_context(parent: str | None = None) -> CorrelationContext:
    """Create a new correlation context with a fresh ID."""
    cid = set_correlation_id()
    return CorrelationContext(correlation_id=cid, parent_span_id=parent)


# ---------------------------------------------------------------------------
# Global run context (module-level, optional)
# ---------------------------------------------------------------------------

_CURRENT_RUN_CONTEXT: RunContext | None = None


def get_run_context() -> RunContext | None:
    """Return the current global RunContext, if one was initialised."""
    return _CURRENT_RUN_CONTEXT


def init_run_context(
    surface: str,
    actor: str = "cli",
    log_root: Path | None = None,
) -> RunContext:
    """Initialise and store the global RunContext.  Idempotent per process."""
    global _CURRENT_RUN_CONTEXT  # noqa: PLW0603
    if _CURRENT_RUN_CONTEXT is not None:
        return _CURRENT_RUN_CONTEXT
    ctx = make_run_context(surface=surface, actor=actor, log_root=log_root)
    _CURRENT_RUN_CONTEXT = ctx
    return ctx


def reset_run_context() -> None:
    """Reset the global RunContext (for tests)."""
    global _CURRENT_RUN_CONTEXT  # noqa: PLW0603
    _CURRENT_RUN_CONTEXT = None


# ---------------------------------------------------------------------------
# Git info helper
# ---------------------------------------------------------------------------


def _collect_git_info() -> dict:
    info: dict = {}
    try:
        branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .decode()
            .strip()
        )
        info["git_branch"] = branch
    except Exception:  # noqa: BLE001
        pass
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .decode()
            .strip()
        )
        info["git_commit"] = commit
    except Exception:  # noqa: BLE001
        pass
    return info


# ---------------------------------------------------------------------------
# README template
# ---------------------------------------------------------------------------

_RUN_README_TEMPLATE = """\
# Run Log — {run_id}

Surface : {surface}
Started : {started_at}

## Files in this directory

| File | Purpose |
|------|---------|
| audit.jsonl     | Meaningful user/system activity trail |
| app.jsonl       | Low-level development/lifecycle logs |
| errors.jsonl    | Exceptions, warnings, degraded-behavior events |
| trace.jsonl     | Workflow/tool/pipeline timeline spans |
| commands.jsonl  | CLI/TUI/chat command execution details |
| ai-agent-summary.md | Human/AI-readable run narrative |
| environment.json | Git branch/commit, Python version, platform info |
| README.md       | This file |

## Content modes

Default is `redacted` — sensitive values are replaced with [REDACTED].
Set `VNALPHA_LOG_CONTENT_MODE=full` for raw content (local debug only).

## Correlation IDs

Every event has a `correlation_id` that groups related audit, trace, command,
app, and error events for a single workflow.
"""
