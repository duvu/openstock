from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from vnalpha.assistant.degraded_answer import (
    AssistantDegradation,
    AssistantFailureStage,
)
from vnalpha.assistant.effective_date import (
    normalize_date_candidate,
    resolve_effective_target_date,
    validate_date_candidate,
)
from vnalpha.assistant.errors import (
    AssistantInputValidationError,
    AssistantLifecycleError,
    RefusalError,
)
from vnalpha.assistant.managed_context import ManagedAssistantContext
from vnalpha.assistant.models import (
    AssistantPlan,
    AssistantRequest,
    PreparedAssistantTurn,
    RefusalMessage,
    plan_hash,
)
from vnalpha.assistant.policy import check_intent_policy, check_policy
from vnalpha.assistant.runtime_helpers import (
    _log_assistant_lifecycle,
    _prompt_projection,
    _refusal_result,
)
from vnalpha.assistant.tool_policy import is_approval_required_plan
from vnalpha.core.text_safety import sanitize_error_summary
from vnalpha.observability.context import get_correlation_id
from vnalpha.sandbox.execution_service import SandboxExecutionService
from vnalpha.warehouse.assistant_repo import (
    create_assistant_session,
    create_llm_trace,
    finish_assistant_session,
    finish_llm_trace,
    mark_assistant_session_prepared,
    persist_prepared_turn,
)
from vnalpha.warehouse.connection import read_connection


class ManagedAssistantPreparation(ManagedAssistantContext):
    def prepare(
        self, request: AssistantRequest
    ) -> PreparedAssistantTurn | tuple[RefusalMessage, AssistantPlan]:
        prompt = request.current_user_prompt
        persistence = _prompt_projection(request)
        try:
            with self._coordinator.transaction() as connection:
                session_id = create_assistant_session(
                    connection,
                    surface=self._surface,
                    user_prompt=persistence.prompt_summary,
                    prompt=persistence,
                )
        except Exception as exc:
            raise AssistantLifecycleError(
                stage=AssistantFailureStage.AUDIT_PERSIST,
                category="SESSION_CREATE_FAILURE",
                correlation_id=get_correlation_id(),
                model_route=self._engine._llm_model(),
            ) from exc
        _log_assistant_lifecycle("ASSISTANT_PREPARED", "prepare", status="RUNNING")
        try:
            request = replace(request, date=normalize_date_candidate(request.date))
            validate_date_candidate(request.date)
            check_policy(prompt)
            with self._coordinator.transaction() as connection:
                classify_trace_id = create_llm_trace(
                    connection,
                    assistant_session_id=session_id,
                    stage="classify",
                    model=self._engine._llm_model(),
                    input_summary={"prompt_chars": len(prompt)},
                )
            try:
                intent_result = self._engine._classifier.classify(
                    prompt,
                    session_id=request.routing_session_id or session_id,
                )
            except Exception as exc:
                try:
                    with self._coordinator.transaction() as connection:
                        finish_llm_trace(
                            connection,
                            classify_trace_id,
                            status="FAILED",
                            error={
                                "message": sanitize_error_summary(exc),
                                **self._engine._raw_response_summary(
                                    self._engine._classifier.last_raw_responses
                                ),
                            },
                        )
                except Exception:
                    _log_assistant_lifecycle(
                        "ASSISTANT_PERSISTENCE_FAILED", "prepare", status="FAILED"
                    )
                raise AssistantLifecycleError(
                    stage=AssistantFailureStage.CLASSIFY,
                    category="CLASSIFICATION_FAILURE",
                    correlation_id=get_correlation_id(),
                    trace_id=classify_trace_id,
                    model_route=self._engine._llm_model(),
                ) from exc
            try:
                with self._coordinator.transaction() as connection:
                    finish_llm_trace(
                        connection,
                        classify_trace_id,
                        status="SUCCESS",
                        output_summary={
                            "intent": intent_result.intent,
                            **self._engine._raw_response_summary(
                                self._engine._classifier.last_raw_responses
                            ),
                        },
                        usage=self._engine._classifier.last_usage,
                    )
            except Exception as exc:
                raise AssistantLifecycleError(
                    stage=AssistantFailureStage.AUDIT_PERSIST,
                    category="CLASSIFY_TRACE_PERSIST_FAILURE",
                    correlation_id=get_correlation_id(),
                    trace_id=classify_trace_id,
                    model_route=self._engine._llm_model(),
                ) from exc
            raw_classified_date = intent_result.entities.get("date")
            classified_date = (
                raw_classified_date if isinstance(raw_classified_date, str) else None
            )
            effective_date = resolve_effective_target_date(
                classified_date=classified_date,
                request_date=request.date,
                intent=intent_result.intent,
                request_date_is_implicit=request.date_is_implicit,
            )
            intent_result.entities["date"] = effective_date
            request = replace(request, date=effective_date)
            check_intent_policy(intent_result)
            try:
                plan = self._engine._planner.build(intent_result)
            except Exception as exc:
                raise AssistantLifecycleError(
                    stage=AssistantFailureStage.PLAN,
                    category="PLAN_BUILD_FAILURE",
                    correlation_id=get_correlation_id(),
                    model_route=self._engine._llm_model(),
                ) from exc
            request = self._with_symbol_memory_context(request, intent_result.entities)
            if is_approval_required_plan(plan):
                with self._coordinator.transaction() as connection:
                    plan = SandboxExecutionService(
                        connection,
                        surface=self._surface,
                    ).materialize_assistant_plan(plan)
            turn = PreparedAssistantTurn(
                prepared_turn_id=f"turn-{uuid4().hex}",
                assistant_session_id=session_id,
                request=request,
                intent_result=intent_result,
                plan=plan,
                plan_hash=plan_hash(plan),
                policy_status="PASS",
                created_at=datetime.now(UTC).isoformat(),
            )
            with self._coordinator.transaction() as connection:
                persist_prepared_turn(connection, turn)
                mark_assistant_session_prepared(
                    connection,
                    session_id,
                    intent=intent_result.intent,
                    plan=plan.to_dict(),
                )
            return turn
        except RefusalError as exc:
            try:
                with self._coordinator.transaction() as connection:
                    finish_assistant_session(
                        connection,
                        session_id,
                        status="REFUSED",
                        refusal_reason=str(exc),
                    )
            except Exception:
                _log_assistant_lifecycle(
                    "ASSISTANT_PERSISTENCE_FAILED", "prepare", status="REFUSED"
                )
            return _refusal_result(exc)
        except AssistantInputValidationError as exc:
            self._finish_prepare_failure(session_id, exc, "VALIDATION_ERROR")
            raise
        except AssistantLifecycleError as exc:
            self._finish_prepare_failure(session_id, exc, "FAILED")
            raise
        except Exception as exc:
            self._finish_prepare_failure(session_id, exc, "FAILED")
            raise AssistantLifecycleError(
                stage=AssistantFailureStage.AUDIT_PERSIST,
                category="PREPARE_PERSIST_FAILURE",
                correlation_id=get_correlation_id(),
                model_route=self._engine._llm_model(),
            ) from exc

    def _with_symbol_memory_context(
        self, request: AssistantRequest, entities: dict[str, Any]
    ) -> AssistantRequest:
        with read_connection(path=self._warehouse_path) as connection:
            return self._connected_engine(connection)._with_symbol_memory_context(
                request, entities
            )

    def _finish_prepare_failure(
        self, session_id: str, exc: Exception, status: str
    ) -> None:
        try:
            with self._coordinator.transaction() as connection:
                finish_assistant_session(
                    connection,
                    session_id,
                    status=status,
                    error={
                        "error_type": type(exc).__name__,
                        "message": sanitize_error_summary(exc),
                        **(
                            {"lifecycle": _lifecycle_diagnostic(exc)}
                            if isinstance(exc, AssistantLifecycleError)
                            else {}
                        ),
                    },
                )
        except Exception:
            _log_assistant_lifecycle(
                "ASSISTANT_PERSISTENCE_FAILED", "prepare", status=status
            )


def _lifecycle_diagnostic(exc: AssistantLifecycleError) -> dict[str, str]:
    return AssistantDegradation(
        exc.stage,
        exc.category,
        correlation_id=exc.correlation_id,
        trace_id=exc.trace_id,
        model_route=exc.model_route,
    ).to_dict()
