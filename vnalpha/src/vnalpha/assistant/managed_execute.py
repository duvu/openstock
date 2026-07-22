from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.degraded_answer import (
    AssistantDegradation,
    AssistantFailureStage,
    with_degradation,
)
from vnalpha.assistant.errors import (
    AssistantLifecycleError,
    PreparedPlanHashMismatchError,
)
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
from vnalpha.observability.context import get_correlation_id
from vnalpha.warehouse.assistant_repo import (
    create_llm_trace,
    finish_assistant_session,
    finish_llm_trace,
    finish_prepared_turn,
)
from vnalpha.warehouse.session_repo import create_tool_trace


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
        try:
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
        except Exception as exc:
            try:
                with self._coordinator.transaction() as connection:
                    finish_prepared_turn(
                        connection, prepared.prepared_turn_id, status="FAILED"
                    )
            except Exception:
                self._record_persistence_failure()
            try:
                with self._coordinator.transaction() as connection:
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
            except Exception:
                self._record_persistence_failure()
            raise AssistantLifecycleError(
                stage=AssistantFailureStage.AUDIT_PERSIST,
                category="TOOL_TRACE_CREATE_FAILURE",
                correlation_id=get_correlation_id(),
                model_route=self._engine._llm_model(),
            ) from exc
        try:
            tool_outputs = self._execute_managed_tools(
                prepared, trace_ids, on_trace_event=on_trace_event
            )
        except Exception as exc:
            lifecycle_error = AssistantLifecycleError(
                stage=AssistantFailureStage.TOOL_EXECUTION,
                category="TOOL_EXECUTION_FAILURE",
                correlation_id=get_correlation_id(),
                trace_id=trace_ids[0] if trace_ids else None,
                model_route=self._engine._llm_model(),
            )
            try:
                with self._coordinator.transaction() as connection:
                    finish_prepared_turn(
                        connection, prepared.prepared_turn_id, status="FAILED"
                    )
            except Exception:
                self._record_persistence_failure()
            try:
                with self._coordinator.transaction() as connection:
                    finish_assistant_session(
                        connection,
                        prepared.assistant_session_id,
                        status="FAILED",
                        intent=prepared.intent_result.intent,
                        plan=prepared.plan.to_dict(),
                        error={
                            "error_type": type(exc).__name__,
                            "message": sanitize_error_summary(exc),
                            "lifecycle": _lifecycle_diagnostic(lifecycle_error),
                        },
                    )
            except Exception:
                self._record_persistence_failure()
            raise lifecycle_error from exc
        synthesis_trace_id: str | None = None
        trace_creation_failed = False
        try:
            with self._coordinator.transaction() as connection:
                synthesis_trace_id = create_llm_trace(
                    connection,
                    assistant_session_id=prepared.assistant_session_id,
                    stage="synthesize",
                    model=self._engine._llm_model(),
                    input_summary={"steps": len(prepared.plan.steps)},
                )
        except Exception:
            trace_creation_failed = True
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
        except Exception as exc:
            lifecycle_error = AssistantLifecycleError(
                stage=AssistantFailureStage.ANSWER_VALIDATION,
                category="SYNTHESIS_FAIL_CLOSED",
                correlation_id=get_correlation_id(),
                trace_id=synthesis_trace_id,
                model_route=self._engine._llm_model(),
            )
            if synthesis_trace_id is not None:
                try:
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
                            model=self._engine._llm_model(),
                        )
                except Exception:
                    self._record_persistence_failure()
            try:
                with self._coordinator.transaction() as connection:
                    finish_prepared_turn(
                        connection, prepared.prepared_turn_id, status="FAILED"
                    )
            except Exception:
                self._record_persistence_failure()
            try:
                with self._coordinator.transaction() as connection:
                    finish_assistant_session(
                        connection,
                        prepared.assistant_session_id,
                        status="FAILED",
                        intent=prepared.intent_result.intent,
                        plan=prepared.plan.to_dict(),
                        error={
                            "error_type": type(exc).__name__,
                            "message": sanitize_error_summary(exc),
                            "lifecycle": _lifecycle_diagnostic(lifecycle_error),
                        },
                    )
            except Exception:
                self._record_persistence_failure()
            raise lifecycle_error from exc
        degradation = self._engine._synthesizer.last_degradation
        session_status = "DEGRADED_SUCCESS" if degradation is not None else "SUCCESS"
        if degradation is not None:
            degradation = AssistantDegradation(
                stage=degradation.stage,
                category=degradation.category,
                trace_id=synthesis_trace_id,
                model_route=self._engine._llm_model(),
            )
            answer = with_degradation(answer, degradation)
        if trace_creation_failed:
            answer = with_degradation(
                answer,
                AssistantDegradation(
                    AssistantFailureStage.AUDIT_PERSIST,
                    "SYNTHESIS_TRACE_CREATE_FAILURE",
                    model_route=self._engine._llm_model(),
                ),
            )
            session_status = "DEGRADED_SUCCESS"
        if synthesis_trace_id is not None:
            try:
                with self._coordinator.transaction() as connection:
                    finish_llm_trace(
                        connection,
                        synthesis_trace_id,
                        status=session_status,
                        output_summary={
                            "summary_length": len(answer.summary),
                            **self._engine._raw_response_summary(
                                self._engine._synthesizer.last_raw_responses
                            ),
                        },
                        usage=self._engine._synthesizer.last_usage,
                        error=degradation.to_dict()
                        if degradation is not None
                        else None,
                        model=self._engine._llm_model(),
                    )
            except Exception:
                answer = with_degradation(
                    answer,
                    AssistantDegradation(
                        AssistantFailureStage.AUDIT_PERSIST,
                        "SYNTHESIS_TRACE_PERSIST_FAILURE",
                        trace_id=synthesis_trace_id,
                        model_route=self._engine._llm_model(),
                    ),
                )
                session_status = "DEGRADED_SUCCESS"
        if is_research_intent(prepared.plan.intent):
            try:
                with self._coordinator.transaction() as connection:
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
            except Exception:
                answer = with_degradation(
                    answer,
                    AssistantDegradation(
                        AssistantFailureStage.AUDIT_PERSIST,
                        "AUDIT_PERSIST_FAILURE",
                        trace_id=synthesis_trace_id,
                        model_route=self._engine._llm_model(),
                    ),
                )
                session_status = "DEGRADED_SUCCESS"
            else:
                try:
                    with self._coordinator.transaction() as connection:
                        projected = self._engine._project_analysis_evidence(
                            prepared.plan, tool_outputs, answer, conn=connection
                        )
                except Exception:
                    projected = False
                if not projected:
                    answer = with_degradation(
                        answer,
                        AssistantDegradation(
                            AssistantFailureStage.KNOWLEDGE_PROJECTION,
                            "KNOWLEDGE_PROJECTION_FAILURE",
                            trace_id=synthesis_trace_id,
                            model_route=self._engine._llm_model(),
                        ),
                    )
                    session_status = "DEGRADED_SUCCESS"
        try:
            with self._coordinator.transaction() as connection:
                finish_prepared_turn(
                    connection, prepared.prepared_turn_id, status="EXECUTED"
                )
        except Exception:
            answer = with_degradation(
                answer,
                AssistantDegradation(
                    AssistantFailureStage.SESSION_FINALIZE,
                    "SESSION_FINALIZE_FAILURE",
                    trace_id=synthesis_trace_id,
                    model_route=self._engine._llm_model(),
                ),
            )
            session_status = "DEGRADED_SUCCESS"
            if synthesis_trace_id is not None:
                try:
                    with self._coordinator.transaction() as connection:
                        finish_llm_trace(
                            connection,
                            synthesis_trace_id,
                            status=session_status,
                            error=answer.research_metadata["degradation"],
                            model=self._engine._llm_model(),
                        )
                except Exception:
                    self._record_persistence_failure()
        try:
            with self._coordinator.transaction() as connection:
                finish_assistant_session(
                    connection,
                    prepared.assistant_session_id,
                    status=session_status,
                    intent=prepared.intent_result.intent,
                    plan=prepared.plan.to_dict(),
                    answer=answer.to_dict(),
                )
        except Exception:
            answer = with_degradation(
                answer,
                AssistantDegradation(
                    AssistantFailureStage.SESSION_FINALIZE,
                    "SESSION_FINALIZE_FAILURE",
                    trace_id=synthesis_trace_id,
                    model_route=self._engine._llm_model(),
                ),
            )
            session_status = "DEGRADED_SUCCESS"
            if synthesis_trace_id is not None:
                try:
                    with self._coordinator.transaction() as connection:
                        finish_llm_trace(
                            connection,
                            synthesis_trace_id,
                            status=session_status,
                            error=answer.research_metadata["degradation"],
                            model=self._engine._llm_model(),
                        )
                except Exception:
                    self._record_persistence_failure()
        _log_assistant_lifecycle(
            "ASSISTANT_EXECUTED", "execute_prepared", status=session_status
        )
        return answer, prepared.plan

    def _record_persistence_failure(self) -> None:
        _log_assistant_lifecycle(
            "ASSISTANT_PERSISTENCE_FAILED", "execute_prepared", status="FAILED"
        )

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


def _lifecycle_diagnostic(exc: AssistantLifecycleError) -> dict[str, str]:
    return AssistantDegradation(
        exc.stage,
        exc.category,
        correlation_id=exc.correlation_id,
        trace_id=exc.trace_id,
        model_route=exc.model_route,
    ).to_dict()
