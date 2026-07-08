"""TypedDict schemas for all observability event types.

Each schema defines required fields per the design spec.
All events share: ts, run_id, correlation_id, event_type.
"""

from __future__ import annotations

from typing_extensions import TypedDict


class BaseEvent(TypedDict):
    event_id: str
    run_id: str
    created_at: str
    level: str
    event_type: str
    surface: str
    correlation_id: str
    status: str
    summary: str
    redaction_status: str


class AuditEvent(TypedDict):
    event_id: str
    run_id: str
    created_at: str
    level: str
    event_type: str
    surface: str
    actor: str
    correlation_id: str
    status: str
    summary: str
    redaction_status: str
    metadata: dict


class AppLogEvent(TypedDict):
    event_id: str
    run_id: str
    created_at: str
    level: str
    event_type: str
    surface: str
    correlation_id: str
    module: str
    function: str
    summary: str
    redaction_status: str


class ErrorEvent(TypedDict):
    event_id: str
    run_id: str
    created_at: str
    level: str
    event_type: str
    surface: str
    correlation_id: str
    error_type: str
    error_message: str
    module: str
    function: str
    stacktrace: str
    stacktrace_hash: str
    likely_cause: str
    suggested_next_step: str
    redaction_status: str


class TraceEvent(TypedDict):
    event_id: str
    run_id: str
    created_at: str
    level: str
    event_type: str
    surface: str
    correlation_id: str
    span_id: str
    parent_span_id: str
    status: str
    started_at: str
    ended_at: str
    duration_ms: float
    module: str
    operation: str
    redaction_status: str


class CommandEvent(TypedDict):
    event_id: str
    run_id: str
    created_at: str
    level: str
    event_type: str
    surface: str
    correlation_id: str
    command: str
    args: str
    status: str
    exit_code: int
    duration_ms: float
    stdout_tail: str
    stderr_tail: str
    redaction_status: str


# Required fields per event type (used for validation in tests)
AUDIT_REQUIRED_FIELDS = frozenset(
    {"event_id", "run_id", "created_at", "level", "event_type", "correlation_id"}
)
APP_LOG_REQUIRED_FIELDS = frozenset(
    {"event_id", "run_id", "created_at", "level", "event_type", "correlation_id"}
)
ERROR_REQUIRED_FIELDS = frozenset(
    {
        "event_id",
        "run_id",
        "created_at",
        "level",
        "event_type",
        "correlation_id",
        "error_type",
        "error_message",
    }
)
TRACE_REQUIRED_FIELDS = frozenset(
    {
        "event_id",
        "run_id",
        "created_at",
        "level",
        "event_type",
        "correlation_id",
        "span_id",
        "status",
    }
)
COMMAND_REQUIRED_FIELDS = frozenset(
    {
        "event_id",
        "run_id",
        "created_at",
        "level",
        "event_type",
        "correlation_id",
        "command",
        "status",
    }
)
