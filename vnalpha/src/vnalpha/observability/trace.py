"""Trace event writer — writes to trace.jsonl."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from vnalpha.observability.context import (
    get_correlation_id,
    get_run_context,
    new_span_id,
)
from vnalpha.observability.jsonl import append_jsonl
from vnalpha.observability.redaction import redaction_status


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_trace(
    event_type: str,
    operation: str,
    *,
    status: str = "OK",
    span_id: str | None = None,
    parent_span_id: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    duration_ms: float | None = None,
    module: str = "",
    level: str = "INFO",
    run_ctx=None,
    extra: dict | None = None,
    mode: str | None = None,
) -> str:
    """Write a trace span event to trace.jsonl.  Returns span_id."""
    try:
        ctx = run_ctx or get_run_context()
        if ctx is None:
            return ""
        sid = span_id or new_span_id()
        now = _now_iso()
        record: dict = {
            "event_id": uuid4().hex,
            "run_id": ctx.run_id,
            "created_at": now,
            "level": level,
            "event_type": event_type,
            "surface": ctx.surface,
            "correlation_id": get_correlation_id(),
            "span_id": sid,
            "parent_span_id": parent_span_id or "",
            "status": status,
            "started_at": started_at or now,
            "ended_at": ended_at or "",
            "duration_ms": duration_ms if duration_ms is not None else 0.0,
            "module": module,
            "operation": operation,
            "redaction_status": redaction_status(mode),
        }
        if extra:
            record.update(extra)
        append_jsonl(ctx.trace_path, record)
        return sid
    except Exception:  # noqa: BLE001
        return ""
