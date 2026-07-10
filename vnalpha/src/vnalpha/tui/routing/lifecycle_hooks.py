"""Controller setup, thread-safe callbacks, and connection ownership hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.executor import CommandExecutor
    from vnalpha.tui.routing.status_adapter import StatusAdapter, TraceEvent
    from vnalpha.tui.widgets.output_stream import OutputStream


@dataclass(frozen=True, slots=True)
class ExecutorResources:
    """The command executor and connection owned by one router."""

    connection: DuckDBPyConnection | None
    executor: CommandExecutor | None


class LifecycleHooks:
    """Keep setup and teardown behavior outside the routing facade."""

    def __init__(
        self,
        output: OutputStream,
        target_date: str | None,
        status: StatusAdapter,
        ui_dispatcher: Callable[[Callable[[], None]], None] | None,
    ) -> None:
        self._output = output
        self._target_date = target_date
        self._status = status
        self._ui_dispatcher = ui_dispatcher

    def bootstrap_session(self) -> str | None:
        try:
            from vnalpha.warehouse.chat_repo import get_or_create_active_chat_session
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.migrations import run_migrations

            connection = get_connection()
            try:
                run_migrations(conn=connection)
                return get_or_create_active_chat_session(
                    connection,
                    surface="tui-workspace",
                    target_date=self._target_date,
                )
            finally:
                connection.close()
        except Exception:
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

            return ChatController(
                target_date=self._target_date,
                on_message=on_message,
                on_trace=on_trace,
                chat_session_id=session_id,
            )
        except Exception:
            return None

    def setup_executor(self) -> ExecutorResources:
        connection: DuckDBPyConnection | None = None
        try:
            from vnalpha.commands.executor import CommandExecutor
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.migrations import run_migrations

            connection = get_connection()
            run_migrations(conn=connection)
            return ExecutorResources(
                connection=connection,
                executor=CommandExecutor(
                    connection,
                    surface="tui",
                    default_date=self._target_date,
                ),
            )
        except Exception:
            if connection is not None:
                connection.close()
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
            connection.close()
