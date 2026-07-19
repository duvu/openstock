"""Top-level orchestrator for the warehouse-grounded research assistant."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

import duckdb

if TYPE_CHECKING:
    from vnalpha.chat.context import ChatContext
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.effective_date import (
    normalize_date_candidate,
    resolve_effective_target_date,
    validate_date_candidate,
)
from vnalpha.assistant.errors import (
    AssistantError,
    AssistantInputValidationError,
    RefusalError,
    SynthesisError,
)
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.intent import IntentClassifier
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    AssistantRequest,
    PreparedAssistantTurn,
    PromptPersistenceRecord,
    RefusalMessage,
    plan_hash,
    text_hash,
)
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.policy import check_intent_policy, check_policy
from vnalpha.assistant.research_templates import is_research_intent
from vnalpha.assistant.synthesizer import AnswerSynthesizer
from vnalpha.assistant.tool_policy import is_approval_required_plan
from vnalpha.core.text_safety import sanitize_error_summary
from vnalpha.data_availability.dates import (
    normalize_optional_date,
)
from vnalpha.warehouse.assistant_repo import (
    create_assistant_session,
    create_llm_trace,
    finish_assistant_session,
    finish_llm_trace,
    finish_prepared_turn,
    mark_assistant_session_prepared,
    persist_prepared_turn,
)
from vnalpha.workspace_context.redaction import redact_workspace_text


def _prompt_projection(request: AssistantRequest) -> PromptPersistenceRecord:
    redacted = redact_workspace_text(request.current_user_prompt).text
    prompt_digest = text_hash(redacted)
    raw_stored = os.environ.get("VNALPHA_ASSISTANT_STORE_RAW", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    workspace_ref = (
        text_hash(request.workspace_context)
        if request.workspace_context is not None
        else None
    )
    chat_payload = (
        json.dumps(request.to_dict()["chat_context"], sort_keys=True)
        if request.chat_context is not None
        else None
    )
    chat_ref = text_hash(chat_payload) if chat_payload is not None else None
    summary = f"prompt chars={len(redacted)} sha256={prompt_digest}"
    return PromptPersistenceRecord(
        prompt_text=redacted if raw_stored else None,
        prompt_summary=summary,
        prompt_hash=prompt_digest,
        prompt_chars=len(redacted),
        workspace_context_ref=workspace_ref,
        chat_context_ref=chat_ref,
        raw_stored=raw_stored,
    )


def _refusal_result(exc: RefusalError) -> tuple[RefusalMessage, AssistantPlan]:
    reason = exc.args[0] if exc.args else str(exc)
    return (
        RefusalMessage(
            reason=reason,
            policy_category=getattr(exc, "policy_category", "UNKNOWN"),
            suggestion=getattr(exc, "suggestion", None),
        ),
        AssistantPlan(
            intent="unsupported_or_unsafe",
            steps=[],
            refusal_reason=reason,
        ),
    )


def _request_as_of_date(value: str | None) -> date:
    normalized = normalize_date_candidate(value)
    return date.fromisoformat(normalize_optional_date(normalized))


class AssistantApp:
    """Orchestrate policy, classification, tools, synthesis, and audit."""

    def __init__(
        self,
        conn,
        *,
        surface: str = "cli",
        llm_client: LLMGatewayClient | None = None,
    ):
        self._conn = conn
        self._surface = surface
        self._llm = llm_client or LLMGatewayClient(LLMGatewayConfig.from_env())
        self._classifier = IntentClassifier(self._llm)
        self._planner = PlanBuilder()
        self._synthesizer = AnswerSynthesizer(self._llm)

    def ask(
        self,
        user_prompt: str,
        *,
        date: str | None = None,
        date_is_implicit: bool | None = None,
        no_execute: bool = False,
        on_trace_event: "Callable[[TraceEvent], None] | None" = None,
        chat_context: "ChatContext | None" = None,
        workspace_context: str | None = None,
    ) -> tuple[AssistantAnswer | RefusalMessage, AssistantPlan]:
        """Process one request through the prepare/execute compatibility path."""

        request = AssistantRequest(
            current_user_prompt=user_prompt,
            workspace_context=workspace_context,
            chat_context=chat_context,
            date=date,
            date_is_implicit=(
                date is None or date.strip().lower() == "today"
                if date_is_implicit is None
                else date_is_implicit
            ),
        )
        prepared = self.prepare(request)
        if isinstance(prepared, tuple):
            return prepared
        if is_approval_required_plan(prepared.plan):
            return self._preview_prepared(prepared)
        if no_execute:
            return self._preview_prepared(prepared)
        return self.execute_prepared(prepared, on_trace_event=on_trace_event)

    def prepare(
        self, request: AssistantRequest
    ) -> PreparedAssistantTurn | tuple[RefusalMessage, AssistantPlan]:
        """Perform safety, classification, policy, and planning exactly once."""

        prompt = request.current_user_prompt
        persistence = _prompt_projection(request)
        session_id = create_assistant_session(
            self._conn,
            surface=self._surface,
            user_prompt=persistence.prompt_summary,
            prompt=persistence,
        )
        try:
            from vnalpha.observability.trace import log_trace

            log_trace("ASSISTANT_PREPARED", "prepare", status="RUNNING")
        except Exception:  # noqa: BLE001
            pass
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
                raise
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
            plan = self._planner.build(intent_result)
            request = self._with_symbol_memory_context(request, intent_result.entities)
            if is_approval_required_plan(plan):
                from vnalpha.sandbox.execution_service import SandboxExecutionService

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
            finish_assistant_session(
                self._conn,
                session_id,
                status="REFUSED",
                refusal_reason=str(exc),
            )
            return _refusal_result(exc)
        except AssistantInputValidationError as exc:
            finish_assistant_session(
                self._conn,
                session_id,
                status="VALIDATION_ERROR",
                error={
                    "error_type": type(exc).__name__,
                    "message": sanitize_error_summary(exc),
                },
            )
            raise
        except AssistantError as exc:
            finish_assistant_session(
                self._conn,
                session_id,
                status="FAILED",
                error={
                    "error_type": type(exc).__name__,
                    "message": sanitize_error_summary(exc),
                },
            )
            raise

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
            from vnalpha.symbol_memory.repository import SymbolMemoryRepository
            from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService

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

    def execute_prepared(
        self,
        prepared: PreparedAssistantTurn,
        *,
        on_trace_event: "Callable[[TraceEvent], None] | None" = None,
        on_synthesizing: "Callable[[], None] | None" = None,
    ) -> tuple[AssistantAnswer | RefusalMessage, AssistantPlan]:
        """Execute the exact prepared plan without reclassification or replanning."""

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
            raise ValueError("Prepared plan hash mismatch; execution refused.")
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
            try:
                from vnalpha.observability.trace import log_trace

                log_trace("ASSISTANT_EXECUTED", "execute_prepared", status="SUCCESS")
            except Exception:  # noqa: BLE001
                pass
            return answer, prepared.plan
        from vnalpha.assistant.executor import AssistantExecutor

        executor = AssistantExecutor(
            self._conn,
            assistant_session_id=prepared.assistant_session_id,
            on_trace_event=on_trace_event,
        )
        try:
            tool_outputs = executor.execute(prepared.plan)
        except Exception as exc:
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
            finish_llm_trace(
                self._conn,
                synthesis_trace_id,
                status="SUCCESS",
                output_summary={
                    "summary_length": len(answer.summary),
                    **self._raw_response_summary(self._synthesizer.last_raw_responses),
                },
                usage=self._synthesizer.last_usage,
            )
        except Exception as exc:
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
        if is_research_intent(prepared.plan.intent):
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
            # The audit above raises unless groundedness and policy both passed,
            # so reaching here means the answer is validated. Project its
            # deterministic evidence into symbol knowledge (issue #164).
            self._project_analysis_evidence(prepared.plan, tool_outputs, answer)
        finish_assistant_session(
            self._conn,
            prepared.assistant_session_id,
            status="SUCCESS",
            intent=prepared.intent_result.intent,
            plan=prepared.plan.to_dict(),
            answer=answer.to_dict(),
        )
        finish_prepared_turn(self._conn, prepared.prepared_turn_id, status="EXECUTED")
        try:
            from vnalpha.observability.trace import log_trace

            log_trace("ASSISTANT_EXECUTED", "execute_prepared", status="SUCCESS")
        except Exception:  # noqa: BLE001
            pass
        return answer, prepared.plan

    def cancel_prepared(self, prepared: PreparedAssistantTurn) -> None:
        """Cancel a prepared turn without executing its plan."""

        finish_prepared_turn(self._conn, prepared.prepared_turn_id, status="CANCELLED")
        finish_assistant_session(
            self._conn,
            prepared.assistant_session_id,
            status="VALIDATION_ERROR",
            error={"error_type": "Cancelled", "message": "prepared turn cancelled"},
        )
        try:
            from vnalpha.observability.trace import log_trace

            log_trace("ASSISTANT_CANCELLED", "cancel_prepared", status="CANCELLED")
        except Exception:  # noqa: BLE001
            pass

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

    def _persist_research_audit(
        self,
        *,
        session_id: str,
        plan: AssistantPlan,
        tool_outputs: dict,
        answer: AssistantAnswer,
    ) -> str:
        groundedness = self._synthesizer.last_groundedness
        policy = self._synthesizer.last_policy
        if groundedness is None or policy is None:
            raise SynthesisError(
                "Research answer validation metadata is unavailable; "
                "the answer cannot be audited."
            )
        if not groundedness.passed or not policy.passed:
            raise SynthesisError(
                "Research answer failed validation and cannot be persisted."
            )
        try:
            from vnalpha.assistant.research_audit import (
                persist_research_answer_audit,
            )

            return persist_research_answer_audit(
                self._conn,
                assistant_session_id=session_id,
                plan=plan,
                tool_outputs=tool_outputs,
                answer=answer,
                groundedness=groundedness,
                policy=policy,
            )
        except SynthesisError:
            raise
        except Exception as exc:
            raise SynthesisError(
                f"Research answer audit persistence failed: {exc}"
            ) from exc

    def _project_analysis_evidence(
        self,
        plan: AssistantPlan,
        tool_outputs: dict,
        answer: AssistantAnswer,
    ) -> None:
        """Project a validated deep-analysis turn's evidence into symbol memory.

        Best-effort and fail-open: a projection failure is recorded on the
        answer's research metadata as a caveat but never fails the validated
        answer (issue #164).
        """
        if plan.intent != "deep_analyze_symbol":
            return
        try:
            from vnalpha.observability.context import get_correlation_id
            from vnalpha.symbol_memory.projection import project_analysis_evidence

            correlation_id = get_correlation_id() or plan.intent
            result = project_analysis_evidence(
                self._conn,
                tool_outputs,
                correlation_id=correlation_id,
            )
        except Exception as exc:  # noqa: BLE001
            from vnalpha.core.logging import get_logger

            get_logger("assistant.app").warning(
                "Symbol knowledge projection failed: %s", exc
            )
            answer.research_metadata = {
                **answer.research_metadata,
                "knowledge_projection": {
                    "projected": [],
                    "warnings": [f"Symbol knowledge projection failed: {exc}"],
                },
            }
            return
        answer.research_metadata = {
            **answer.research_metadata,
            "knowledge_projection": result.to_trace_dict(),
        }

    def _llm_model(self) -> str:
        config = getattr(self._llm, "config", None)
        model = getattr(config, "model", None)
        return str(model or type(self._llm).__name__)

    def _raw_response_summary(
        self, raw_responses: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        config = getattr(self._llm, "config", None)
        if not getattr(config, "store_raw", False):
            return {}
        return {"raw_responses": raw_responses}
