from __future__ import annotations

from vnalpha.assistant.connected_context import ConnectedAssistantContext
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    PreparedAssistantTurn,
)
from vnalpha.assistant.runtime_helpers import _log_assistant_lifecycle
from vnalpha.warehouse.assistant_repo import (
    finish_assistant_session,
    finish_prepared_turn,
)


class ConnectedAssistantControls(ConnectedAssistantContext):
    def cancel_prepared(self, prepared: PreparedAssistantTurn) -> None:
        """Cancel a prepared turn without executing its plan."""

        if self._managed_runtime is not None:
            self._managed_runtime.cancel_prepared(prepared)
            return

        finish_prepared_turn(self._conn, prepared.prepared_turn_id, status="CANCELLED")
        finish_assistant_session(
            self._conn,
            prepared.assistant_session_id,
            status="VALIDATION_ERROR",
            error={"error_type": "Cancelled", "message": "prepared turn cancelled"},
        )
        _log_assistant_lifecycle(
            "ASSISTANT_CANCELLED", "cancel_prepared", status="CANCELLED"
        )

    def _preview_prepared(
        self, prepared: PreparedAssistantTurn
    ) -> tuple[AssistantAnswer, AssistantPlan]:
        finish_assistant_session(
            self._conn,
            prepared.assistant_session_id,
            status="SUCCESS",
            intent=prepared.intent_result.intent,
            plan=prepared.plan.to_dict(),
        )
        finish_prepared_turn(self._conn, prepared.prepared_turn_id, status="PREVIEWED")
        return (
            AssistantAnswer(
                summary=(
                    "[Plan preview — not executed]\n"
                    f"{self._planner.preview(prepared.plan)}"
                ),
                basis="Plan preview only.",
                risks_caveats="",
                tool_trace_summary="No tools executed (--no-execute mode).",
            ),
            prepared.plan,
        )
