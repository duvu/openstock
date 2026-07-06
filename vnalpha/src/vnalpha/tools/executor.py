"""Traced execution wrapper for local research tools."""

from __future__ import annotations

import dataclasses
from typing import Any

from vnalpha.tools.models import ToolPermission
from vnalpha.tools.registry import LocalToolRegistry
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
    ) -> None:
        self._conn = conn
        self._registry = registry
        self._session_id = session_id
        self._assistant_session_id = assistant_session_id
        self._trace_parent_type = trace_parent_type

    def call(
        self,
        name: str,
        granted_permissions: set[ToolPermission] | None = None,
        **kwargs: Any,
    ):
        """Call a local tool and persist success/failure trace rows."""
        spec = self._registry.get_spec(name)
        granted = granted_permissions or {spec.permission}
        trace_id = create_tool_trace(
            self._conn,
            session_id=self._session_id,
            assistant_session_id=self._assistant_session_id,
            trace_parent_type=self._trace_parent_type,
            tool_name=name,
            input_data=_json_safe(kwargs),
        )
        try:
            output = self._registry.call(name, granted, **kwargs)
            finish_tool_trace(
                self._conn,
                trace_id,
                status="SUCCESS",
                output_summary=_summarize_output(output),
            )
            return output
        except Exception as exc:
            finish_tool_trace(
                self._conn,
                trace_id,
                status="FAILED",
                error={"message": str(exc), "error_type": type(exc).__name__},
            )
            raise


def _summarize_output(output: Any) -> dict[str, Any]:
    if dataclasses.is_dataclass(output):
        data = dataclasses.asdict(output)
        payload = data.get("data")
        rows = len(payload) if isinstance(payload, list) else None
        return {"summary": data.get("summary"), "rows": rows}
    return {"result": str(output)[:200]}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
