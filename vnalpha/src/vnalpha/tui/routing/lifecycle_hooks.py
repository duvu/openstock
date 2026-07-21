"""Controller setup, thread-safe callbacks, and connection ownership hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.coordinated_executor import CoordinatedCommandExecutor
    from vnalpha.commands.executor import CommandExecutor
    from vnalpha.tui.routing.status_adapter import StatusAdapter, TraceEvent
    from vnalpha.tui.widgets.output_stream import OutputStream


def _capture_exception_safely(exc: Exception) -> None:
    try:
        from vnalpha.observability.errors import capture_exception

        capture_exception(exc)
    except Exception:  # noqa: BLE001
        pass


@dataclass(frozen=True, slots=True)
class ExecutorResources:
    """The command executor and connection owned by one router."""

    connection: DuckDBPyConnection | None
    executor: CommandExecutor | CoordinatedCommandExecutor | None


class LifecycleHooks:
    """Keep setup and teardown behavior outside the routing facade."""

    def __init__(
        self,
        output: OutputStream,
        target_date: str | None,
        target_date_is_implicit: bool,
        status: StatusAdapter,
        ui_dispatcher: Callable[[Callable[[], None]], None] | None,
    ) -> None:
        self._output = output
        self._target_date = target_date
        self._target_date_is_implicit = target_date_is_implicit
        self._status = status
        self._ui_dispatcher = ui_dispatcher

    def bootstrap_session(self) -> str | None:
        try:
            from vnalpha.warehouse.chat_repo import get_or_create_active_chat_session
            from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

            with WarehouseWriteCoordinator().transaction() as connection:
                return get_or_create_active_chat_session(
                    connection,
                    surface="tui-workspace",
                    target_date=self._target_date,
                )
        except Exception as exc:
            _capture_exception_safely(exc)
            return None

    def setup_controller(self, session_id: str | None) -> ChatController | None:
        try:
            from vnalpha.chat.controller import ChatController

            def on_message(style: str, text: str) -> None:
                self.dispatch_ui(
                    lambda: self._output.show_assistant_message(
                        text, style=style or None
                    )
                )

            def on_trace(event: TraceEvent) -> None:
                self.dispatch_ui(lambda: self.render_trace(event))

            def on_assistant_answer(answer: object) -> None:
                self.dispatch_ui(
                    lambda: self._output.append_assistant_answer(
                        self._coerce_assistant_answer(answer)
                    )
                )

            return ChatController(
                target_date=self._target_date,
                target_date_is_implicit=self._target_date_is_implicit,
                on_message=on_message,
                on_trace=on_trace,
                on_assistant_answer=on_assistant_answer,
                chat_session_id=session_id,
            )
        except Exception as exc:
            _capture_exception_safely(exc)
            return None

    def _coerce_assistant_answer(self, answer: object) -> object:
        from vnalpha.assistant.models import AssistantAnswer

        if isinstance(answer, AssistantAnswer):
            from vnalpha.tui.models.conversation import AssistantAnswerMessage

            return AssistantAnswerMessage(
                text=answer.summary,
                summary=answer.summary,
                basis=answer.basis,
                risks_caveats=answer.risks_caveats,
                missing_data=answer.missing_data,
                grounded_source_refs=answer.grounded_source_refs,
                claim_source_refs=answer.claim_source_refs,
                research_metadata=answer.research_metadata,
                tool_trace_summary=answer.tool_trace_summary,
            )

        return answer  # type: ignore[return-value]

    def setup_executor(self) -> ExecutorResources:
        try:
            from vnalpha.commands.coordinated_executor import (
                CoordinatedCommandExecutor,
            )

            return ExecutorResources(
                connection=None,
                executor=CoordinatedCommandExecutor(
                    surface="tui",
                    default_date=self._target_date,
                    default_date_is_implicit=self._target_date_is_implicit,
                ),
            )
        except Exception as exc:
            _capture_exception_safely(exc)
            return ExecutorResources(connection=None, executor=None)

    def dispatch_ui(self, callback: Callable[[], None]) -> None:
        if self._ui_dispatcher is None:
            callback()
            return
        self._ui_dispatcher(callback)

    def render_trace(self, event: TraceEvent) -> None:
        self._output.show_trace_event(event)
        self._status.trace(event)

    def close_connection(self, connection: DuckDBPyConnection | None) -> None:
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                _capture_exception_safely(exc)
