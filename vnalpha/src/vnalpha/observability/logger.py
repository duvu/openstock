"""App log writer — writes to app.jsonl."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from vnalpha.observability.context import get_correlation_id, get_run_context
from vnalpha.observability.jsonl import append_jsonl
from vnalpha.observability.redaction import redact_dict, redaction_status


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_app(
    event_type: str,
    summary: str,
    *,
    level: str = "INFO",
    module: str = "",
    function: str = "",
    run_ctx=None,
    extra: dict | None = None,
    mode: str | None = None,
) -> None:
    """Write an app-level log event to app.jsonl.  Best-effort: never raises."""
    try:
        ctx = run_ctx or get_run_context()
        if ctx is None:
            return
        record: dict = {
            "event_id": uuid4().hex,
            "run_id": ctx.run_id,
            "created_at": _now_iso(),
            "level": level,
            "event_type": event_type,
            "surface": ctx.surface,
            "correlation_id": get_correlation_id(),
            "module": module,
            "function": function,
            "summary": summary,
            "redaction_status": redaction_status(mode),
        }
        if extra:
            record.update(redact_dict(extra, mode))
        append_jsonl(ctx.app_path, record)
    except Exception:  # noqa: BLE001
        pass
