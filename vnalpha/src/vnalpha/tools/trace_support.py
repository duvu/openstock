from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TraceEvent:
    tool_name: str
    status: str
    duration_ms: float | None
    tool_trace_id: str


@dataclass(frozen=True, slots=True)
class PendingToolTrace:
    trace_id: str
    tool_name: str
    input_data: dict[str, Any]
    status: str
    output_summary: dict[str, Any] | None = None
    error: dict[str, str] | None = None


def summarize_output(output: Any) -> dict[str, Any]:
    if dataclasses.is_dataclass(output):
        data = dataclasses.asdict(output)
        payload = data.get("data")
        rows = len(payload) if isinstance(payload, list) else None
        return {"summary": data.get("summary"), "rows": rows}
    return {"result": str(output)[:200]}


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
