from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.errors import PreparedPlanHashMismatchError
from vnalpha.assistant.managed_context import ManagedAssistantContext
from vnalpha.assistant.managed_failures import finish_execution_failure
from vnalpha.assistant.managed_sandbox import ManagedAssistantSandboxExecution
from vnalpha.assistant.managed_tools import ManagedAssistantToolExecution
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    PreparedAssistantTurn,
    RefusalMessage,
    plan_hash,
)
from vnalpha.assistant.research_templates import is_research_intent
from vnalpha.assistant.runtime_helpers import _log_assistant_lifecycle
from vnalpha.assistant.tool_policy import is_approval_required_plan
from vnalpha.core.text_safety import sanitize_error_summary
from vnalpha.warehouse.assistant_repo import (
    create_llm_trace,
    finish_assistant_session,
    finish_llm_trace,
    finish_prepared_turn,
)


class ManagedAssistantExecution(
    ManagedAssistantToolExecution,
    ManagedAssistantSandboxExecution,
    ManagedAssistantContext,
):
    def execute_prepared(
        self,
        prepared: PreparedAssistantTurn,
        *,
        on_trace_event: "Callable[[TraceEvent], None] | None" = None,
        on_synthesizing: "Callable[[], None] | None" = None,
    ) -> tuple[AssistantAnswer | RefusalMessage, AssistantPlan]:
        if plan_hash(prepared.plan) != prepared.plan_hash:
            with self._coordinator.transaction() as connection:
                finish_prepared_turn(
                    connection, prepared.prepared_turn_id, status="HASH_MISMATCH"
                )
                finish_assistant_session(
                    connection,
                    prepared.assistant_session_id,
                    status="VALIDATION_ERROR",
                    error={
                        "error_type": "PlanHashMismatch",
                        "message": "prepared plan changed",
                    },
                )
            raise PreparedPlanHashMismatchError(
                "Prepared plan hash mismatch; execution refused."
            )
        if is_approval_required_plan(prepared.plan):
            return self._execute_coordinated_sandbox(
                prepared,
                on_trace_event=on_trace_event,
            )
        from vnalpha.warehouse.session_repo import create_tool_trace

        with self._coordinator.transaction() as connection:
            trace_ids = tuple(
                create_tool_trace(
                    connection,
                    session_id=None,
                    assistant_session_id=prepared.assistant_session_id,
                    trace_parent_type="assistant",
                    tool_name=step.tool_name,
                    input_data=step.arguments,
                )
                for step in prepared.plan.steps
            )
        tool_outputs = self._execute_managed_tools(
            prepared, trace_ids, on_trace_event=on_trace_event
        )
        with self._coordinator.transaction() as connection:
            synthesis_trace_id = create_llm_trace(
                connection,
                assistant_session_id=prepared.assistant_session_id,
                stage="synthesize",
                model=self._engine._llm_model(),
                input_summary={"steps": len(prepared.plan.steps)},
            )
        if on_synthesizing is not None:
            on_synthesizing()
        try:
            answer = self._engine._synthesizer.synthesize(
                prepared.request.current_user_prompt,
                prepared.plan,
                tool_outputs,
                request=prepared.request,
                session_id=(
                    prepared.request.routing_session_id or prepared.assistant_session_id
                ),
            )
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK
            with self._coordinator.transaction() as connection:
                finish_llm_trace(
                    connection,
                    synthesis_trace_id,
                    status="FAILED",
                    error={
                        "message": sanitize_error_summary(exc),
                        **self._engine._raw_response_summary(
                            self._engine._synthesizer.last_raw_responses
                        ),
                    },
                )
                finish_prepared_turn(
                    connection, prepared.prepared_turn_id, status="FAILED"
                )
                finish_assistant_session(
                    connection,
                    prepared.assistant_session_id,
                    status="FAILED",
                    intent=prepared.intent_result.intent,
                    plan=prepared.plan.to_dict(),
                    error={
                        "error_type": type(exc).__name__,
                        "message": sanitize_error_summary(exc),
                    },
                )
            raise
        with self._coordinator.transaction() as connection:
            finish_llm_trace(
                connection,
                synthesis_trace_id,
                status="SUCCESS",
                output_summary={
                    "summary_length": len(answer.summary),
                    **self._engine._raw_response_summary(
                        self._engine._synthesizer.last_raw_responses
                    ),
                },
                usage=self._engine._synthesizer.last_usage,
            )
            if is_research_intent(prepared.plan.intent):
                audit_id = self._engine._persist_research_audit(
                    session_id=prepared.assistant_session_id,
                    plan=prepared.plan,
                    tool_outputs=tool_outputs,
                    answer=answer,
                    conn=connection,
                )
                answer.research_metadata = {
                    **answer.research_metadata,
                    "research_answer_audit_id": audit_id,
                }
                self._engine._project_analysis_evidence(
                    prepared.plan, tool_outputs, answer, conn=connection
                )
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

    def _finish_execution_failure(
        self, prepared: PreparedAssistantTurn, exc: Exception
    ) -> None:
        with self._coordinator.transaction() as connection:
            finish_execution_failure(connection, prepared, exc)

    def _preview_prepared(
        self, prepared: PreparedAssistantTurn
    ) -> tuple[AssistantAnswer, AssistantPlan]:
        with self._coordinator.transaction() as connection:
            return self._connected_engine(connection)._preview_prepared(prepared)

    def cancel_prepared(self, prepared: PreparedAssistantTurn) -> None:
        with self._coordinator.transaction() as connection:
            self._connected_engine(connection).cancel_prepared(prepared)
