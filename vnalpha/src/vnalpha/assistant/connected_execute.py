from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.connected_context import ConnectedAssistantContext
from vnalpha.assistant.degraded_answer import (
    AssistantDegradation,
    AssistantFailureStage,
    with_degradation,
)
from vnalpha.assistant.errors import PreparedPlanHashMismatchError
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    PreparedAssistantTurn,
    RefusalMessage,
    plan_hash,
)
from vnalpha.assistant.research_templates import is_research_intent
from vnalpha.assistant.tool_policy import is_approval_required_plan
from vnalpha.core.text_safety import sanitize_error_summary
from vnalpha.warehouse.assistant_repo import (
    create_llm_trace,
    finish_assistant_session,
    finish_llm_trace,
    finish_prepared_turn,
)


class ConnectedAssistantExecution(ConnectedAssistantContext):
    def execute_prepared(
        self,
        prepared: PreparedAssistantTurn,
        *,
        on_trace_event: "Callable[[TraceEvent], None] | None" = None,
        on_synthesizing: "Callable[[], None] | None" = None,
    ) -> tuple[AssistantAnswer | RefusalMessage, AssistantPlan]:
        """Execute the exact prepared plan without reclassification or replanning."""

        if self._managed_runtime is not None:
            return self._managed_runtime.execute_prepared(
                prepared,
                on_trace_event=on_trace_event,
                on_synthesizing=on_synthesizing,
            )

        if plan_hash(prepared.plan) != prepared.plan_hash:
            finish_prepared_turn(
                self._conn, prepared.prepared_turn_id, status="HASH_MISMATCH"
            )
            finish_assistant_session(
                self._conn,
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
            from vnalpha.sandbox.execution_service import SandboxExecutionService

            answer = SandboxExecutionService(
                self._conn,
                surface=self._surface,
            ).execute_prepared_turn(prepared)
            finish_assistant_session(
                self._conn,
                prepared.assistant_session_id,
                status="SUCCESS",
                intent=prepared.intent_result.intent,
                plan=prepared.plan.to_dict(),
                answer=answer.to_dict(),
            )
            finish_prepared_turn(
                self._conn, prepared.prepared_turn_id, status="EXECUTED"
            )
            from vnalpha.assistant.runtime_helpers import _log_assistant_lifecycle

            _log_assistant_lifecycle(
                "ASSISTANT_EXECUTED", "execute_prepared", status="SUCCESS"
            )
            return answer, prepared.plan
        from vnalpha.assistant.executor import AssistantExecutor

        executor = AssistantExecutor(
            self._conn,
            assistant_session_id=prepared.assistant_session_id,
            on_trace_event=on_trace_event,
        )
        try:
            tool_outputs = executor.execute(prepared.plan)
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK
            finish_assistant_session(
                self._conn,
                prepared.assistant_session_id,
                status="FAILED",
                intent=prepared.intent_result.intent,
                plan=prepared.plan.to_dict(),
                error={
                    "error_type": type(exc).__name__,
                    "message": sanitize_error_summary(exc),
                },
            )
            finish_prepared_turn(self._conn, prepared.prepared_turn_id, status="FAILED")
            raise
        if on_synthesizing is not None:
            on_synthesizing()
        synthesis_trace_id = create_llm_trace(
            self._conn,
            assistant_session_id=prepared.assistant_session_id,
            stage="synthesize",
            model=self._llm_model(),
            input_summary={"steps": len(prepared.plan.steps)},
        )
        try:
            answer = self._synthesizer.synthesize(
                prepared.request.current_user_prompt,
                prepared.plan,
                tool_outputs,
                request=prepared.request,
                session_id=(
                    prepared.request.routing_session_id or prepared.assistant_session_id
                ),
            )
            degradation = self._synthesizer.last_degradation
            session_status = (
                "DEGRADED_SUCCESS" if degradation is not None else "SUCCESS"
            )
            if degradation is not None:
                degradation = AssistantDegradation(
                    stage=degradation.stage,
                    category=degradation.category,
                    trace_id=synthesis_trace_id,
                    model_route=self._llm_model(),
                )
                answer = with_degradation(
                    answer,
                    degradation,
                )
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK
            finish_llm_trace(
                self._conn,
                synthesis_trace_id,
                status="FAILED",
                error={
                    "message": sanitize_error_summary(exc),
                    **self._raw_response_summary(self._synthesizer.last_raw_responses),
                },
            )
            finish_prepared_turn(self._conn, prepared.prepared_turn_id, status="FAILED")
            raise
        try:
            finish_llm_trace(
                self._conn,
                synthesis_trace_id,
                status=session_status,
                output_summary={
                    "summary_length": len(answer.summary),
                    **self._raw_response_summary(self._synthesizer.last_raw_responses),
                },
                usage=self._synthesizer.last_usage,
                error=degradation.to_dict() if degradation is not None else None,
            )
        except Exception:  # noqa: BROAD_EXCEPT_OK
            answer = with_degradation(
                answer,
                AssistantDegradation(
                    AssistantFailureStage.SYNTHESIS_PERSIST,
                    "SYNTHESIS_TRACE_PERSIST_FAILURE",
                    trace_id=synthesis_trace_id,
                    model_route=self._llm_model(),
                ),
            )
            session_status = "DEGRADED_SUCCESS"
        if is_research_intent(prepared.plan.intent):
            try:
                audit_id = self._persist_research_audit(
                    session_id=prepared.assistant_session_id,
                    plan=prepared.plan,
                    tool_outputs=tool_outputs,
                    answer=answer,
                )
                answer.research_metadata = {
                    **answer.research_metadata,
                    "research_answer_audit_id": audit_id,
                }
            except Exception:  # noqa: BROAD_EXCEPT_OK
                answer = with_degradation(
                    answer,
                    AssistantDegradation(
                        AssistantFailureStage.AUDIT_PERSIST,
                        "AUDIT_PERSIST_FAILURE",
                        trace_id=synthesis_trace_id,
                        model_route=self._llm_model(),
                    ),
                )
                session_status = "DEGRADED_SUCCESS"
            else:
                try:
                    projected = self._project_analysis_evidence(
                        prepared.plan, tool_outputs, answer
                    )
                except Exception:  # noqa: BROAD_EXCEPT_OK
                    projected = False
                if not projected:
                    answer = with_degradation(
                        answer,
                        AssistantDegradation(
                            AssistantFailureStage.KNOWLEDGE_PROJECTION,
                            "KNOWLEDGE_PROJECTION_FAILURE",
                            trace_id=synthesis_trace_id,
                            model_route=self._llm_model(),
                        ),
                    )
                    session_status = "DEGRADED_SUCCESS"
        try:
            finish_assistant_session(
                self._conn,
                prepared.assistant_session_id,
                status=session_status,
                intent=prepared.intent_result.intent,
                plan=prepared.plan.to_dict(),
                answer=answer.to_dict(),
            )
            finish_prepared_turn(
                self._conn, prepared.prepared_turn_id, status="EXECUTED"
            )
        except Exception:  # noqa: BROAD_EXCEPT_OK
            answer = with_degradation(
                answer,
                AssistantDegradation(
                    AssistantFailureStage.SESSION_FINALIZE,
                    "SESSION_FINALIZE_FAILURE",
                    trace_id=synthesis_trace_id,
                    model_route=self._llm_model(),
                ),
            )
            session_status = "DEGRADED_SUCCESS"
        from vnalpha.assistant.runtime_helpers import _log_assistant_lifecycle

        _log_assistant_lifecycle(
            "ASSISTANT_EXECUTED", "execute_prepared", status=session_status
        )
        return answer, prepared.plan
