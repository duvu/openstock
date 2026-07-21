from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vnalpha.assistant.models import (
        AssistantAnswer,
        AssistantPlan,
        PreparedAssistantTurn,
        RefusalMessage,
    )
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.managed_context import ManagedAssistantContext
from vnalpha.assistant.managed_failures import finish_execution_failure
from vnalpha.assistant.runtime_helpers import _log_assistant_lifecycle
from vnalpha.warehouse.assistant_repo import (
    finish_assistant_session,
    finish_prepared_turn,
)


class ManagedAssistantSandboxExecution(ManagedAssistantContext):
    def _execute_coordinated_sandbox(
        self,
        prepared: PreparedAssistantTurn,
        *,
        on_trace_event: Callable[[TraceEvent], None] | None,
    ) -> tuple[AssistantAnswer | RefusalMessage, AssistantPlan]:
        del on_trace_event
        from vnalpha.sandbox.execution_service import SandboxExecutionService

        try:
            with self._coordinator.transaction() as connection:
                answer = SandboxExecutionService(
                    connection, surface=self._surface
                ).execute_prepared_turn(prepared)
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK
            with self._coordinator.transaction() as connection:
                finish_execution_failure(connection, prepared, exc)
            raise
        with self._coordinator.transaction() as connection:
            finish_assistant_session(
                connection,
                prepared.assistant_session_id,
                status="SUCCESS",
                intent=prepared.intent_result.intent,
                plan=prepared.plan.to_dict(),
                answer=answer.to_dict(),
            )
            finish_prepared_turn(
                connection, prepared.prepared_turn_id, status="EXECUTED"
            )
        _log_assistant_lifecycle(
            "ASSISTANT_EXECUTED", "execute_prepared", status="SUCCESS"
        )
        return answer, prepared.plan
