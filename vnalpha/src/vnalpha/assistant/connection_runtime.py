"""Top-level orchestrator for the warehouse-grounded research assistant."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vnalpha.chat.context import ChatContext
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.connected_controls import ConnectedAssistantControls
from vnalpha.assistant.connected_execute import ConnectedAssistantExecution
from vnalpha.assistant.connected_persistence import ConnectedAssistantPersistence
from vnalpha.assistant.connected_prepare import ConnectedAssistantPreparation
from vnalpha.assistant.gateway import LLMGatewayClient
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    AssistantRequest,
    RefusalMessage,
)
from vnalpha.assistant.tool_policy import is_approval_required_plan


class AssistantApp(
    ConnectedAssistantPreparation,
    ConnectedAssistantExecution,
    ConnectedAssistantControls,
    ConnectedAssistantPersistence,
):
    """Orchestrate policy, classification, tools, synthesis, and audit."""

    @classmethod
    def managed(
        cls,
        *,
        surface: str = "cli",
        llm_client: LLMGatewayClient | None = None,
        warehouse_path: Path | str | None = None,
    ) -> AssistantApp:
        from vnalpha.assistant.managed_runtime import ManagedAssistantRuntime

        app = cls(None, surface=surface, llm_client=llm_client)
        app._managed_runtime = ManagedAssistantRuntime(
            surface=surface,
            llm_client=app._llm,
            warehouse_path=warehouse_path,
        )
        return app

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

        if self._managed_runtime is not None:
            return self._managed_runtime.ask(
                user_prompt,
                date=date,
                date_is_implicit=date_is_implicit,
                no_execute=no_execute,
                on_trace_event=on_trace_event,
                chat_context=chat_context,
                workspace_context=workspace_context,
            )

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
