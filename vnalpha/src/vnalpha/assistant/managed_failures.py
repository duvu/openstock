from __future__ import annotations

from vnalpha.assistant.models import AssistantPlan, PreparedAssistantTurn
from vnalpha.core.text_safety import sanitize_error_summary
from vnalpha.tools.setup import TOOL_PERMISSIONS
from vnalpha.warehouse.assistant_repo import (
    finish_assistant_session,
    finish_prepared_turn,
)
from vnalpha.warehouse.session_repo import finish_tool_trace


def write_tool_names(plan: AssistantPlan) -> tuple[str, ...]:
    return tuple(
        step.tool_name
        for step in plan.steps
        if TOOL_PERMISSIONS[step.tool_name].value.startswith("WRITE_")
    )


def finish_execution_failure(
    connection,
    prepared: PreparedAssistantTurn,
    exc: Exception,
    *,
    trace_ids: tuple[str, ...] = (),
) -> None:
    error = {
        "error_type": type(exc).__name__,
        "message": sanitize_error_summary(exc),
    }
    for trace_id in trace_ids:
        finish_tool_trace(
            connection,
            trace_id,
            status="FAILED",
            error=error,
        )
    finish_assistant_session(
        connection,
        prepared.assistant_session_id,
        status="FAILED",
        intent=prepared.intent_result.intent,
        plan=prepared.plan.to_dict(),
        error=error,
    )
    finish_prepared_turn(connection, prepared.prepared_turn_id, status="FAILED")
