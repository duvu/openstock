"""Traced execution wrapper for local research tools."""

from __future__ import annotations

import time
from typing import Any, Callable

from vnalpha.core.text_safety import sanitize_error_summary
from vnalpha.tools.errors import DeferredToolTraceStateError, ToolPermissionError
from vnalpha.tools.models import ToolPermission
from vnalpha.tools.registry import LocalToolRegistry
from vnalpha.tools.trace_support import (
    PendingToolTrace,
    TraceEvent,
    json_safe,
    summarize_output,
)
from vnalpha.warehouse.session_repo import create_tool_trace, finish_tool_trace


class TracedLocalToolExecutor:
    """Execute LocalToolRegistry calls while persisting tool_trace rows."""

    def __init__(
        self,
        conn,
        registry: LocalToolRegistry,
        *,
        session_id: str | None = None,
        assistant_session_id: str | None = None,
        trace_parent_type: str = "command",
        trace_event_callback: Callable[[TraceEvent], None] | None = None,
        deferred: bool = False,
        prestarted_trace_ids: tuple[str, ...] = (),
    ) -> None:
        self._conn = conn
        self._registry = registry
        self._session_id = session_id
        self._assistant_session_id = assistant_session_id
        self._trace_parent_type = trace_parent_type
        self._trace_event_callback = trace_event_callback
        self._deferred = deferred
        self._pending_traces: list[PendingToolTrace] = []
        self._prestarted_trace_ids = list(prestarted_trace_ids)
        self._all_prestarted_trace_ids = frozenset(prestarted_trace_ids)

    def call(
        self,
        name: str,
        granted_permissions: set[ToolPermission] | None = None,
        **kwargs: Any,
    ):
        """Call a local tool and persist success/failure trace rows."""
        spec = self._registry.get_spec(name)
        granted = granted_permissions or {spec.permission}
        input_data = json_safe(kwargs)
        if self._deferred:
            if not self._prestarted_trace_ids:
                raise DeferredToolTraceStateError(
                    "Deferred tool execution requires a started trace."
                )
            trace_id = self._prestarted_trace_ids.pop(0)
        else:
            trace_id = create_tool_trace(
                self._conn,
                session_id=self._session_id,
                assistant_session_id=self._assistant_session_id,
                trace_parent_type=self._trace_parent_type,
                tool_name=name,
                input_data=input_data,
            )

        # Emit RUNNING event
        if self._trace_event_callback is not None:
            self._trace_event_callback(
                TraceEvent(
                    tool_name=name,
                    status="RUNNING",
                    duration_ms=None,
                    tool_trace_id=trace_id,
                )
            )
        try:
            from vnalpha.observability.trace import log_trace

            log_trace(
                "TOOL_CALL_STARTED", name, status="RUNNING", module="vnalpha.tools"
            )
        except Exception:  # noqa: BLE001
            pass

        start = time.monotonic()
        try:
            output = self._registry.call(name, granted, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000
            self._finish_trace(
                trace_id,
                tool_name=name,
                input_data=input_data,
                status="SUCCESS",
                output_summary=summarize_output(output),
            )
            # Emit SUCCESS event
            if self._trace_event_callback is not None:
                self._trace_event_callback(
                    TraceEvent(
                        tool_name=name,
                        status="SUCCESS",
                        duration_ms=duration_ms,
                        tool_trace_id=trace_id,
                    )
                )
            try:
                from vnalpha.observability.trace import log_trace

                log_trace(
                    "TOOL_CALL_SUCCEEDED",
                    name,
                    status="SUCCESS",
                    duration_ms=duration_ms,
                    module="vnalpha.tools",
                )
            except Exception:  # noqa: BLE001
                pass
            return output
        except ToolPermissionError as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._finish_trace(
                trace_id,
                tool_name=name,
                input_data=input_data,
                status="FAILED",
                error={
                    "message": sanitize_error_summary(exc),
                    "error_type": type(exc).__name__,
                },
            )
            if self._trace_event_callback is not None:
                self._trace_event_callback(
                    TraceEvent(
                        tool_name=name,
                        status="FAILED",
                        duration_ms=duration_ms,
                        tool_trace_id=trace_id,
                    )
                )
            try:
                from vnalpha.observability.audit import log_audit
                from vnalpha.observability.trace import log_trace

                log_audit(
                    "TOOL_REFUSED",
                    f"Tool '{name}' refused: {exc}",
                    module="vnalpha.tools",
                )
                log_trace(
                    "TOOL_CALL_REFUSED",
                    name,
                    status="FAILED",
                    duration_ms=duration_ms,
                    module="vnalpha.tools",
                )
            except Exception:  # noqa: BLE001
                pass
            raise
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._finish_trace(
                trace_id,
                tool_name=name,
                input_data=input_data,
                status="FAILED",
                error={
                    "message": sanitize_error_summary(exc),
                    "error_type": type(exc).__name__,
                },
            )
            # Emit FAILED event
            if self._trace_event_callback is not None:
                self._trace_event_callback(
                    TraceEvent(
                        tool_name=name,
                        status="FAILED",
                        duration_ms=duration_ms,
                        tool_trace_id=trace_id,
                    )
                )
            try:
                from vnalpha.observability.errors import capture_exception
                from vnalpha.observability.trace import log_trace

                log_trace(
                    "TOOL_CALL_FAILED",
                    name,
                    status="FAILED",
                    duration_ms=duration_ms,
                    module="vnalpha.tools",
                )
                capture_exception(exc)
            except Exception:  # noqa: BLE001
                pass
            raise

    def _finish_trace(
        self,
        trace_id: str,
        *,
        tool_name: str,
        input_data: dict[str, Any],
        status: str,
        output_summary: dict[str, Any] | None = None,
        error: dict[str, str] | None = None,
    ) -> None:
        if self._deferred:
            self._pending_traces.append(
                PendingToolTrace(
                    trace_id=trace_id,
                    tool_name=tool_name,
                    input_data=input_data,
                    status=status,
                    output_summary=output_summary,
                    error=error,
                )
            )
            return
        finish_tool_trace(
            self._conn,
            trace_id,
            status=status,
            output_summary=output_summary,
            error=error,
        )

    def flush(self, conn) -> None:
        for trace in self._pending_traces:
            if trace.trace_id not in self._all_prestarted_trace_ids:
                create_tool_trace(
                    conn,
                    session_id=self._session_id,
                    assistant_session_id=self._assistant_session_id,
                    trace_parent_type=self._trace_parent_type,
                    tool_name=trace.tool_name,
                    input_data=trace.input_data,
                    trace_id=trace.trace_id,
                )
            finish_tool_trace(
                conn,
                trace.trace_id,
                status=trace.status,
                output_summary=trace.output_summary,
                error=trace.error,
                input_data=trace.input_data,
            )
        for trace_id in self._prestarted_trace_ids:
            finish_tool_trace(
                conn,
                trace_id,
                status="FAILED",
                error={
                    "error_type": "ToolNotExecuted",
                    "message": "Command ended before the planned tool call.",
                },
            )
        self._pending_traces.clear()
        self._prestarted_trace_ids.clear()
