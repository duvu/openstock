from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vnalpha.chat.context import ChatContext
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.managed_execute import ManagedAssistantExecution
from vnalpha.assistant.managed_prepare import ManagedAssistantPreparation
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    AssistantRequest,
    RefusalMessage,
)
from vnalpha.assistant.tool_policy import is_approval_required_plan


class ManagedAssistantRuntime(ManagedAssistantPreparation, ManagedAssistantExecution):
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
        if is_approval_required_plan(prepared.plan) or no_execute:
            return self._preview_prepared(prepared)
        return self.execute_prepared(prepared, on_trace_event=on_trace_event)
