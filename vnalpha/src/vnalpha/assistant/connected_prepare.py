from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import duckdb

from vnalpha.assistant.connected_context import ConnectedAssistantContext
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
    AssistantError,
    AssistantInputValidationError,
    AssistantLifecycleError,
    RefusalError,
)
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
    _request_as_of_date,
)
from vnalpha.assistant.tool_policy import is_approval_required_plan
from vnalpha.core.text_safety import sanitize_error_summary
from vnalpha.observability.context import get_correlation_id
from vnalpha.sandbox.execution_service import SandboxExecutionService
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.warehouse.assistant_repo import (
    create_assistant_session,
    create_llm_trace,
    finish_assistant_session,
    finish_llm_trace,
    mark_assistant_session_prepared,
    persist_prepared_turn,
)


class ConnectedAssistantPreparation(ConnectedAssistantContext):
    def prepare(
        self, request: AssistantRequest
    ) -> PreparedAssistantTurn | tuple[RefusalMessage, AssistantPlan]:
        if self._managed_runtime is not None:
            return self._managed_runtime.prepare(request)

        prompt = request.current_user_prompt
        persistence = _prompt_projection(request)
        try:
            session_id = create_assistant_session(
                self._conn,
                surface=self._surface,
                user_prompt=persistence.prompt_summary,
                prompt=persistence,
            )
        except Exception as exc:
            raise AssistantLifecycleError(
                stage=AssistantFailureStage.AUDIT_PERSIST,
                category="SESSION_CREATE_FAILURE",
                correlation_id=get_correlation_id(),
                model_route=self._llm_model(),
            ) from exc
        _log_assistant_lifecycle("ASSISTANT_PREPARED", "prepare", status="RUNNING")
        try:
            request = replace(request, date=normalize_date_candidate(request.date))
            validate_date_candidate(request.date)
            check_policy(prompt)
            classify_trace_id = create_llm_trace(
                self._conn,
                assistant_session_id=session_id,
                stage="classify",
                model=self._llm_model(),
                input_summary={"prompt_chars": len(prompt)},
            )
            try:
                intent_result = self._classifier.classify(
                    prompt,
                    session_id=request.routing_session_id or session_id,
                )
            except Exception as exc:
                try:
                    finish_llm_trace(
                        self._conn,
                        classify_trace_id,
                        status="FAILED",
                        error={
                            "message": sanitize_error_summary(exc),
                            **self._raw_response_summary(
                                self._classifier.last_raw_responses
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
                    model_route=self._llm_model(),
                ) from exc
            try:
                finish_llm_trace(
                    self._conn,
                    classify_trace_id,
                    status="SUCCESS",
                    output_summary={
                        "intent": intent_result.intent,
                        **self._raw_response_summary(
                            self._classifier.last_raw_responses
                        ),
                    },
                    usage=self._classifier.last_usage,
                )
            except Exception as exc:
                raise AssistantLifecycleError(
                    stage=AssistantFailureStage.AUDIT_PERSIST,
                    category="CLASSIFY_TRACE_PERSIST_FAILURE",
                    correlation_id=get_correlation_id(),
                    trace_id=classify_trace_id,
                    model_route=self._llm_model(),
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
                plan = self._planner.build(intent_result)
            except Exception as exc:
                raise AssistantLifecycleError(
                    stage=AssistantFailureStage.PLAN,
                    category="PLAN_BUILD_FAILURE",
                    correlation_id=get_correlation_id(),
                    model_route=self._llm_model(),
                ) from exc
            request = self._with_symbol_memory_context(request, intent_result.entities)
            if is_approval_required_plan(plan):
                plan = SandboxExecutionService(
                    self._conn,
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
            persist_prepared_turn(self._conn, turn)
            mark_assistant_session_prepared(
                self._conn,
                session_id,
                intent=intent_result.intent,
                plan=plan.to_dict(),
            )
            return turn
        except RefusalError as exc:
            try:
                finish_assistant_session(
                    self._conn,
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
            try:
                finish_assistant_session(
                    self._conn,
                    session_id,
                    status="VALIDATION_ERROR",
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
                    "ASSISTANT_PERSISTENCE_FAILED",
                    "prepare",
                    status="VALIDATION_ERROR",
                )
            raise
        except AssistantError as exc:
            try:
                finish_assistant_session(
                    self._conn,
                    session_id,
                    status="FAILED",
                    error={
                        "error_type": type(exc).__name__,
                        "message": sanitize_error_summary(exc),
                    },
                )
            except Exception:
                _log_assistant_lifecycle(
                    "ASSISTANT_PERSISTENCE_FAILED", "prepare", status="FAILED"
                )
            raise
        except Exception as exc:
            try:
                finish_assistant_session(
                    self._conn,
                    session_id,
                    status="FAILED",
                    error={
                        "error_type": type(exc).__name__,
                        "message": sanitize_error_summary(exc),
                    },
                )
            except Exception:
                _log_assistant_lifecycle(
                    "ASSISTANT_PERSISTENCE_FAILED", "prepare", status="FAILED"
                )
            raise AssistantLifecycleError(
                stage=AssistantFailureStage.AUDIT_PERSIST,
                category="PREPARE_PERSIST_FAILURE",
                correlation_id=get_correlation_id(),
                model_route=self._llm_model(),
            ) from exc

    def _with_symbol_memory_context(
        self, request: AssistantRequest, entities: dict[str, Any]
    ) -> AssistantRequest:
        raw_symbols = entities.get("symbols", ())
        symbols = (
            (raw_symbols,)
            if isinstance(raw_symbols, str)
            else tuple(symbol for symbol in raw_symbols if isinstance(symbol, str))
            if isinstance(raw_symbols, list | tuple)
            else ()
        )
        if not symbols:
            return request
        as_of_date = _request_as_of_date(request.date)
        try:
            retrieval = SymbolMemoryRetrievalService(SymbolMemoryRepository(self._conn))
            rendered = tuple(
                retrieval.render_context(
                    retrieval.retrieve(symbol, as_of_date=as_of_date)
                )
                for symbol in symbols
            )
        except (duckdb.Error, ValueError):
            return request
        memory_context = "\n\n".join(rendered)
        if not memory_context:
            return request
        workspace_context = "\n\n".join(
            value for value in (request.workspace_context, memory_context) if value
        )
        return replace(request, workspace_context=workspace_context)


def _lifecycle_diagnostic(exc: AssistantLifecycleError) -> dict[str, str]:
    return AssistantDegradation(
        exc.stage,
        exc.category,
        correlation_id=exc.correlation_id,
        trace_id=exc.trace_id,
        model_route=exc.model_route,
    ).to_dict()
