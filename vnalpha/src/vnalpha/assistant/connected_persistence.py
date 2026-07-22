from __future__ import annotations

from typing import Any

from vnalpha.assistant.connected_context import ConnectedAssistantContext
from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan


class ConnectedAssistantPersistence(ConnectedAssistantContext):
    def _persist_research_audit(
        self,
        *,
        session_id: str,
        plan: AssistantPlan,
        tool_outputs: dict,
        answer: AssistantAnswer,
        conn=None,
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
                conn if conn is not None else self._conn,
                assistant_session_id=session_id,
                plan=plan,
                tool_outputs=tool_outputs,
                answer=answer,
                groundedness=groundedness,
                policy=policy,
            )
        except SynthesisError:
            raise
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK
            raise SynthesisError(
                f"Research answer audit persistence failed: {exc}"
            ) from exc

    def _project_analysis_evidence(
        self,
        plan: AssistantPlan,
        tool_outputs: dict,
        answer: AssistantAnswer,
        conn=None,
    ) -> bool:
        """Project a validated deep-analysis turn's evidence into symbol memory.

        Best-effort and fail-open: a projection failure is recorded on the
        answer's research metadata as a caveat but never fails the validated
        answer (issue #164).
        """
        if plan.intent != "deep_analyze_symbol":
            return True
        try:
            from vnalpha.observability.context import get_correlation_id
            from vnalpha.symbol_memory.projection import project_analysis_evidence

            correlation_id = get_correlation_id() or plan.intent
            result = project_analysis_evidence(
                conn if conn is not None else self._conn,
                tool_outputs,
                correlation_id=correlation_id,
            )
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK, BLE001
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
            return False
        answer.research_metadata = {
            **answer.research_metadata,
            "knowledge_projection": result.to_trace_dict(),
        }
        return True

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
