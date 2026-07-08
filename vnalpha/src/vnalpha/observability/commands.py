"""Command event writer — writes to commands.jsonl."""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator
from uuid import uuid4

from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import (
    RunContext,
    get_correlation_id,
    get_run_context,
    set_correlation_id,
)
from vnalpha.observability.errors import capture_exception
from vnalpha.observability.jsonl import append_jsonl
from vnalpha.observability.redaction import redact_str, redaction_status

_MAX_OUTPUT_BYTES = 2048  # 2 KB tail limit


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail(text: str, max_bytes: int = _MAX_OUTPUT_BYTES) -> str:
    """Return the last *max_bytes* characters of *text*."""
    if len(text) <= max_bytes:
        return text
    return "…" + text[-max_bytes:]


def log_command_start(
    command: str,
    args: str = "",
    *,
    run_ctx=None,
    mode: str | None = None,
) -> str:
    """Write COMMAND_STARTED to commands.jsonl.  Returns event_id."""
    try:
        ctx = run_ctx or get_run_context()
        if ctx is None:
            return ""
        eid = uuid4().hex
        record: dict = {
            "event_id": eid,
            "run_id": ctx.run_id,
            "created_at": _now_iso(),
            "level": "INFO",
            "event_type": "COMMAND_STARTED",
            "surface": ctx.surface,
            "correlation_id": get_correlation_id(),
            "command": redact_str(command, mode),
            "args": redact_str(args, mode),
            "status": "STARTED",
            "exit_code": None,
            "duration_ms": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "redaction_status": redaction_status(mode),
        }
        append_jsonl(ctx.commands_path, record)
        return eid
    except Exception:  # noqa: BLE001
        return ""


def log_command_success(
    command: str,
    args: str = "",
    *,
    duration_ms: float = 0.0,
    exit_code: int = 0,
    stdout_tail: str = "",
    stderr_tail: str = "",
    run_ctx=None,
    mode: str | None = None,
) -> None:
    """Write COMMAND_SUCCEEDED to commands.jsonl and audit.jsonl."""
    try:
        ctx = run_ctx or get_run_context()
        if ctx is None:
            return
        record: dict = {
            "event_id": uuid4().hex,
            "run_id": ctx.run_id,
            "created_at": _now_iso(),
            "level": "INFO",
            "event_type": "COMMAND_SUCCEEDED",
            "surface": ctx.surface,
            "correlation_id": get_correlation_id(),
            "command": redact_str(command, mode),
            "args": redact_str(args, mode),
            "status": "SUCCESS",
            "exit_code": exit_code,
            "duration_ms": round(duration_ms, 2),
            "stdout_tail": _tail(redact_str(stdout_tail, mode)),
            "stderr_tail": _tail(redact_str(stderr_tail, mode)),
            "redaction_status": redaction_status(mode),
        }
        append_jsonl(ctx.commands_path, record)
        log_audit(
            "COMMAND_EXECUTED",
            f"Command succeeded: {command}",
            status="OK",
            run_ctx=ctx,
            mode=mode,
        )
    except Exception:  # noqa: BLE001
        pass


def log_command_failure(
    command: str,
    args: str = "",
    *,
    duration_ms: float = 0.0,
    exit_code: int = 1,
    stdout_tail: str = "",
    stderr_tail: str = "",
    error_message: str = "",
    run_ctx=None,
    mode: str | None = None,
) -> None:
    """Write COMMAND_FAILED to commands.jsonl and audit.jsonl."""
    try:
        ctx = run_ctx or get_run_context()
        if ctx is None:
            return
        record: dict = {
            "event_id": uuid4().hex,
            "run_id": ctx.run_id,
            "created_at": _now_iso(),
            "level": "ERROR",
            "event_type": "COMMAND_FAILED",
            "surface": ctx.surface,
            "correlation_id": get_correlation_id(),
            "command": redact_str(command, mode),
            "args": redact_str(args, mode),
            "status": "FAILED",
            "exit_code": exit_code,
            "duration_ms": round(duration_ms, 2),
            "stdout_tail": _tail(redact_str(stdout_tail, mode)),
            "stderr_tail": _tail(redact_str(stderr_tail, mode)),
            "error_message": redact_str(error_message, mode),
            "redaction_status": redaction_status(mode),
        }
        append_jsonl(ctx.commands_path, record)
        log_audit(
            "COMMAND_FAILED",
            f"Command failed: {command}",
            status="FAILED",
            level="ERROR",
            run_ctx=ctx,
            mode=mode,
        )
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Restore logging stub (task 9.6)
# ---------------------------------------------------------------------------


def log_restore_event(
    event_type: str,
    summary: str,
    *,
    run_ctx: RunContext | None = None,
    status: str = "OK",
    backup_path: str = "",
    restore_target: str = "",
    mode: str = "redacted",
) -> None:
    """Log a warehouse-restore event to commands.jsonl and audit.jsonl.

    Stub — wired once ``openstock-restore-warehouse`` script is created.
    Until then this function is a no-op placeholder so callers can be
    written and tested before the shell script exists.

    Args:
        event_type:    e.g. ``RESTORE_STARTED``, ``RESTORE_COMPLETED``, ``RESTORE_FAILED``
        summary:       human-readable description
        run_ctx:       active RunContext (uses thread-local default if None)
        status:        OK | FAILED | STARTED
        backup_path:   source backup file being restored
        restore_target: destination warehouse path
        mode:          redaction mode
    """
    # TODO(9.6): implement when openstock-restore-warehouse script is added.
    # When implemented, mirror the pattern from log_command_start / log_command_end:
    # write a record to run_ctx.commands_path and call log_audit().
    pass


@contextmanager
def command_lifecycle(
    command: str,
    args: str = "",
    *,
    run_ctx: RunContext | None = None,
    mode: str | None = None,
) -> Generator[None, None, None]:
    """Context manager that emits COMMAND_STARTED/SUCCEEDED/FAILED and captures exceptions.

    Usage::

        with command_lifecycle("sync symbols"):
            do_work()

    On normal exit:   COMMAND_SUCCEEDED written with duration_ms.
    On exception:     exception captured to errors.jsonl, COMMAND_FAILED written, exception re-raised.
    Correlation ID is generated if not already set.
    """
    ctx = run_ctx or get_run_context()
    if ctx is None:
        yield
        return

    if get_correlation_id() in ("", "unset"):
        set_correlation_id()

    log_command_start(command, args, run_ctx=ctx, mode=mode)
    t0 = time.monotonic()
    try:
        yield
    except Exception as exc:
        duration_ms = (time.monotonic() - t0) * 1000
        capture_exception(exc, run_ctx=ctx, mode=mode)
        log_command_failure(
            command,
            args,
            duration_ms=duration_ms,
            exit_code=1,
            error_message=str(exc),
            run_ctx=ctx,
            mode=mode,
        )
        raise
    else:
        duration_ms = (time.monotonic() - t0) * 1000
        log_command_success(
            command,
            args,
            duration_ms=duration_ms,
            exit_code=0,
            run_ctx=ctx,
            mode=mode,
        )
