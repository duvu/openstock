"""Top-level orchestrator for the warehouse-grounded research assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vnalpha.chat.context import ChatContext
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.context import prefix_assistant_prompt
from vnalpha.assistant.errors import AssistantError, RefusalError, SynthesisError
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.intent import IntentClassifier
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    RefusalMessage,
)
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.policy import check_intent_policy, check_policy
from vnalpha.assistant.research_templates import is_research_intent
from vnalpha.assistant.synthesizer import AnswerSynthesizer
from vnalpha.warehouse.assistant_repo import (
    create_assistant_session,
    create_llm_trace,
    finish_assistant_session,
    finish_llm_trace,
)


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
        no_execute: bool = False,
        on_trace_event: "Callable[[TraceEvent], None] | None" = None,
        chat_context: "ChatContext | None" = None,
        workspace_context: str | None = None,
    ) -> tuple[AssistantAnswer | RefusalMessage, AssistantPlan]:
        """Process one natural-language research question."""

        user_prompt = prefix_assistant_prompt(
            user_prompt,
            workspace_context,
            chat_context,
        )
        session_id = create_assistant_session(
            self._conn,
            surface=self._surface,
            user_prompt=user_prompt,
        )

        try:
            from vnalpha.observability.trace import log_trace

            log_trace(
                "ASSISTANT_ASK_STARTED",
                "ask",
                status="RUNNING",
                module="vnalpha.assistant",
            )
        except Exception:  # noqa: BLE001
            pass

        try:
            result = self._run(
                user_prompt,
                session_id,
                date=date,
                no_execute=no_execute,
                on_trace_event=on_trace_event,
            )
            answer, _plan = result
            try:
                from vnalpha.observability.audit import log_audit
                from vnalpha.observability.trace import log_trace

                answer_type = type(answer).__name__
                summary_chars = len(getattr(answer, "summary", "") or "")
                log_trace(
                    "ASSISTANT_ASK_COMPLETED",
                    "ask",
                    status="SUCCESS",
                    module="vnalpha.assistant",
                    extra={
                        "answer_type": answer_type,
                        "summary_chars": summary_chars,
                    },
                )
                log_audit(
                    "ASSISTANT_ANSWER_LOGGED",
                    f"Answer type={answer_type} summary_chars={summary_chars}",
                    module="vnalpha.assistant",
                )
            except Exception:  # noqa: BLE001
                pass
            return result
        except RefusalError as exc:
            finish_assistant_session(
                self._conn,
                session_id,
                status="REFUSED",
                refusal_reason=exc.args[0] if exc.args else str(exc),
            )
            try:
                from vnalpha.observability.audit import log_audit

                log_audit(
                    "CHAT_REFUSAL",
                    f"AssistantApp refusal: {str(exc)[:120]}",
                    module="vnalpha.assistant",
                )
            except Exception:  # noqa: BLE001
                pass
            return RefusalMessage(
                reason=exc.args[0] if exc.args else str(exc),
                policy_category=(
                    exc.policy_category
                    if hasattr(exc, "policy_category")
                    else "UNKNOWN"
                ),
                suggestion=exc.suggestion if hasattr(exc, "suggestion") else None,
            ), AssistantPlan(
                intent="unsupported_or_unsafe",
                steps=[],
                refusal_reason=str(exc),
            )
        except AssistantError as exc:
            finish_assistant_session(
                self._conn,
                session_id,
                status="FAILED",
                error={"error_type": type(exc).__name__, "message": str(exc)},
            )
            try:
                from vnalpha.observability.errors import capture_exception

                capture_exception(exc)
            except Exception:  # noqa: BLE001
                pass
            raise
        except Exception as exc:
            finish_assistant_session(
                self._conn,
                session_id,
                status="FAILED",
                error={"error_type": "RuntimeError", "message": str(exc)},
            )
            try:
                from vnalpha.observability.errors import capture_exception

                capture_exception(exc)
            except Exception:  # noqa: BLE001
                pass
            raise

    def _run(
        self,
        user_prompt: str,
        session_id: str,
        *,
        date: str | None = None,
        no_execute: bool = False,
        on_trace_event: "Callable[[TraceEvent], None] | None" = None,
    ) -> tuple[AssistantAnswer | RefusalMessage, AssistantPlan]:
        # 1. Deterministic safety check
        check_policy(user_prompt)

        # 2. Classify intent
        classify_trace_id = create_llm_trace(
            self._conn,
            assistant_session_id=session_id,
            stage="classify",
            model=self._llm_model(),
            input_summary={"prompt_chars": len(user_prompt)},
        )
        try:
            intent_result = self._classifier.classify(user_prompt)
            finish_llm_trace(
                self._conn,
                classify_trace_id,
                status="SUCCESS",
                output_summary={"intent": intent_result.intent},
                usage=self._classifier.last_usage,
            )
        except Exception as exc:
            finish_llm_trace(
                self._conn,
                classify_trace_id,
                status="FAILED",
                error={"message": str(exc)},
            )
            raise

        if date and "date" not in intent_result.entities:
            intent_result.entities["date"] = date

        # 3. Post-classification policy check
        check_intent_policy(intent_result)

        # 4. Deterministic plan
        plan = self._planner.build(intent_result)

        if no_execute:
            finish_assistant_session(
                self._conn,
                session_id,
                status="SUCCESS",
                intent=intent_result.intent,
                plan=plan.to_dict(),
            )
            return AssistantAnswer(
                summary=(
                    "[Plan preview — not executed]\n"
                    f"{self._planner.preview(plan)}"
                ),
                basis="Plan preview only.",
                risks_caveats="",
                tool_trace_summary="No tools executed (--no-execute mode).",
            ), plan

        # 5. Execute deterministic tools
        from vnalpha.assistant.executor import AssistantExecutor

        executor = AssistantExecutor(
            self._conn,
            assistant_session_id=session_id,
            on_trace_event=on_trace_event,
        )
        tool_outputs = executor.execute(plan)

        # 6. Synthesize and validate
        synthesis_trace_id = create_llm_trace(
            self._conn,
            assistant_session_id=session_id,
            stage="synthesize",
            model=self._llm_model(),
            input_summary={"steps": len(plan.steps)},
        )
        try:
            answer = self._synthesizer.synthesize(
                user_prompt,
                plan,
                tool_outputs,
            )
            finish_llm_trace(
                self._conn,
                synthesis_trace_id,
                status="SUCCESS",
                output_summary={
                    "summary_length": len(answer.summary),
                    "groundedness_status": (
                        self._synthesizer.last_groundedness.status
                        if self._synthesizer.last_groundedness
                        else None
                    ),
                    "policy_status": (
                        self._synthesizer.last_policy.status
                        if self._synthesizer.last_policy
                        else None
                    ),
                    "fallback_used": self._synthesizer.last_fallback_used,
                },
                usage=self._synthesizer.last_usage,
            )
        except Exception as exc:
            finish_llm_trace(
                self._conn,
                synthesis_trace_id,
                status="FAILED",
                error={"message": str(exc)},
            )
            raise

        # 7. Persist a dedicated deep-research audit before returning the answer.
        if is_research_intent(plan.intent):
            audit_id = self._persist_research_audit(
                session_id=session_id,
                plan=plan,
                tool_outputs=tool_outputs,
                answer=answer,
            )
            answer.research_metadata = {
                **answer.research_metadata,
                "research_answer_audit_id": audit_id,
            }

        # 8. Persist final session result
        finish_assistant_session(
            self._conn,
            session_id,
            status="SUCCESS",
            intent=intent_result.intent,
            plan=plan.to_dict(),
            answer=answer.to_dict(),
        )
        return answer, plan

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

    def _llm_model(self) -> str:
        config = getattr(self._llm, "config", None)
        model = getattr(config, "model", None)
        return str(model or type(self._llm).__name__)
