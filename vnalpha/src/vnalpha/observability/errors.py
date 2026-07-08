"""Error capture helper — writes to errors.jsonl."""

from __future__ import annotations

import hashlib
import sys
import traceback
from datetime import datetime, timezone
from uuid import uuid4

from vnalpha.observability.context import get_correlation_id, get_run_context
from vnalpha.observability.jsonl import append_jsonl
from vnalpha.observability.redaction import redact_str, redaction_status


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def capture_exception(
    exc: BaseException,
    context: dict | None = None,
    run_ctx=None,
    *,
    likely_cause: str = "",
    suggested_next: str = "",
    level: str = "ERROR",
    mode: str | None = None,
) -> None:
    """Capture *exc* and write an error event to errors.jsonl.

    Best-effort: never raises.  Swallowed exceptions are still written.
    """
    try:
        ctx = run_ctx or get_run_context()
        if ctx is None:
            return

        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        tb_hash = hashlib.md5(tb_str.encode("utf-8", errors="replace")).hexdigest()  # noqa: S324

        # Extract module + function from innermost frame
        module = ""
        function = ""
        tb_obj = exc.__traceback__
        while tb_obj is not None:
            frame = tb_obj.tb_frame
            module = frame.f_globals.get("__name__", "")
            function = frame.f_code.co_name
            tb_obj = tb_obj.tb_next

        # Redact stacktrace in non-full modes
        safe_tb = redact_str(tb_str, mode)
        safe_msg = redact_str(str(exc), mode)

        record: dict = {
            "event_id": uuid4().hex,
            "run_id": ctx.run_id,
            "created_at": _now_iso(),
            "level": level,
            "event_type": "EXCEPTION_CAPTURED",
            "surface": ctx.surface,
            "correlation_id": get_correlation_id(),
            "error_type": type(exc).__name__,
            "error_message": safe_msg,
            "module": module,
            "function": function,
            "stacktrace": safe_tb,
            "stacktrace_hash": tb_hash,
            "likely_cause": likely_cause,
            "suggested_next_step": suggested_next,
            "redaction_status": redaction_status(mode),
        }
        if context:
            record["context"] = context
        append_jsonl(ctx.errors_path, record)
    except Exception:  # noqa: BLE001
        try:
            sys.stderr.write("[observability] capture_exception itself failed\n")
        except Exception:  # noqa: BLE001
            pass


def capture_warning(
    message: str,
    *,
    event_type: str = "WARNING",
    run_ctx=None,
    module: str = "",
    function: str = "",
    mode: str | None = None,
) -> None:
    """Write a warning event to errors.jsonl.  Best-effort: never raises."""
    try:
        ctx = run_ctx or get_run_context()
        if ctx is None:
            return
        record: dict = {
            "event_id": uuid4().hex,
            "run_id": ctx.run_id,
            "created_at": _now_iso(),
            "level": "WARNING",
            "event_type": event_type,
            "surface": ctx.surface,
            "correlation_id": get_correlation_id(),
            "error_type": "Warning",
            "error_message": redact_str(message, mode),
            "module": module,
            "function": function,
            "stacktrace": "",
            "stacktrace_hash": "",
            "likely_cause": "",
            "suggested_next_step": "",
            "redaction_status": redaction_status(mode),
        }
        append_jsonl(ctx.errors_path, record)
    except Exception:  # noqa: BLE001
        pass
