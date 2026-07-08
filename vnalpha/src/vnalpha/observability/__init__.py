"""vnalpha observability package.

Public exports for file-based structured logging and AI-agent observability.
"""

from __future__ import annotations

from vnalpha.observability.audit import log_audit
from vnalpha.observability.commands import (
    log_command_failure,
    log_command_start,
    log_command_success,
)
from vnalpha.observability.context import (
    CorrelationContext,
    RunContext,
    get_correlation_id,
    get_run_context,
    init_run_context,
    make_run_context,
    reset_run_context,
    set_correlation_id,
)
from vnalpha.observability.errors import capture_exception, capture_warning
from vnalpha.observability.logger import log_app
from vnalpha.observability.trace import log_trace

__all__ = [
    "RunContext",
    "CorrelationContext",
    "get_run_context",
    "init_run_context",
    "make_run_context",
    "reset_run_context",
    "get_correlation_id",
    "set_correlation_id",
    "log_app",
    "log_audit",
    "capture_exception",
    "capture_warning",
    "log_trace",
    "log_command_start",
    "log_command_success",
    "log_command_failure",
]
