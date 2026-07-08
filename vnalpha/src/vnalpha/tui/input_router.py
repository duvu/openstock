"""TuiInputRouter — routes composer input to CommandExecutor or ChatController."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.tui.widgets.status_bar import StatusBar


class TuiInputRouter:
    """
    Routes text submitted by the ComposerInput to the correct handler.

    Routing rules
    -------------
    empty                  → no-op
    /clear                 → output_stream.clear_visible()
    /approve or approve    → ChatController.approve_pending_plan()
    /cancel  or cancel     → ChatController.cancel_pending_plan()
    starts with /          → CommandExecutor.execute(text)
    otherwise              → ChatController.handle_turn(text)

    All routing decisions emit observability events (TUI_COMMAND_ROUTED /
    TUI_CHAT_ROUTED). Execution errors are emitted to OutputStream and
    captured via observability (TUI_RENDER_ERROR).
    """

    def __init__(
        self,
        output_stream: "OutputStream",
        target_date: str | None = None,
        on_busy_change: Callable[[bool], None] | None = None,
        status_bar: "StatusBar | None" = None,
    ) -> None:
        self._output = output_stream
        self._target_date = target_date
        self._on_busy_change = on_busy_change
        self._status_bar = status_bar
        self._busy = False
        self._chat_controller = None
        self._command_executor = None
        self._setup_controller()
        self._setup_executor()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _bootstrap_session(self) -> str | None:
        try:
            from vnalpha.warehouse.chat_repo import get_or_create_active_chat_session
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.migrations import run_migrations

            conn = get_connection()
            try:
                run_migrations(conn=conn)
                return get_or_create_active_chat_session(
                    conn,
                    surface="tui-workspace",
                    target_date=self._target_date,
                )
            finally:
                conn.close()
        except Exception:
            return None

    def _setup_controller(self) -> None:
        try:
            from vnalpha.chat.controller import ChatController

            session_id = self._bootstrap_session()

            def _on_message(style: str, text: str) -> None:
                self._output.show_assistant_message(text, style=style or None)

            def _on_trace(event) -> None:
                self._output.show_trace_event(event)
                self._update_trace_status(event)

            self._chat_controller = ChatController(
                target_date=self._target_date,
                on_message=_on_message,
                on_trace=_on_trace,
                chat_session_id=session_id,
            )
        except Exception:
            self._chat_controller = None

    def _setup_executor(self) -> None:
        try:
            from vnalpha.commands.executor import CommandExecutor
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.migrations import run_migrations

            conn = get_connection()
            run_migrations(conn=conn)
            self._command_executor = CommandExecutor(
                conn,
                surface="tui",
                default_date=self._target_date,
            )
        except Exception:
            self._command_executor = None

    # ------------------------------------------------------------------
    # Public routing entry point
    # ------------------------------------------------------------------

    async def route(self, text: str) -> None:
        """Route ``text`` to the appropriate handler (async, thread-safe)."""
        raw = text.strip()
        if not raw:
            return

        # Echo user input
        self._output.show_user_input(raw)

        # Routing shortcuts
        if raw == "/clear":
            self._output.clear_visible()
            return
        if raw in ("/approve", "approve"):
            self._handle_approve()
            return
        if raw in ("/cancel", "cancel"):
            self._handle_cancel()
            return
        if raw == "a" and self._has_pending_plan():
            self._handle_approve()
            return
        if raw in ("n", "no") and self._has_pending_plan():
            self._handle_cancel()
            return

        if self._busy:
            self._output.show_warning("Still processing, please wait…", source="router")
            return

        self._set_busy(True)
        self._set_status_routing()
        try:
            if raw.startswith("/"):
                await self._route_command(raw)
            else:
                await self._route_chat(raw)
        except Exception as exc:
            self._set_status_error(str(exc))
            self._output.show_error(str(exc), source="router")
            self._capture_render_error(exc)
        finally:
            self._set_busy(False)

    # ------------------------------------------------------------------
    # Command path
    # ------------------------------------------------------------------

    async def _route_command(self, raw: str) -> None:
        """Execute a slash command via CommandExecutor and render result."""
        self._emit_routed("command", raw)
        self._set_status_command(raw)
        try:
            if self._command_executor is None:
                self._output.show_error("CommandExecutor unavailable.", source="router")
                self._set_status_error("CommandExecutor unavailable")
                return
            result = await asyncio.to_thread(self._command_executor.execute, raw)
            markup = self._result_to_markup(result)
            self._output.show_command_result(raw, markup)
            # Check for warnings in result
            warnings = getattr(result, "warnings", None)
            if warnings:
                self._set_status_warning("; ".join(warnings[:2]))
            else:
                self._set_status_ready()
        except Exception as exc:
            self._output.show_error(str(exc), source="command")
            self._set_status_error(str(exc))
            self._capture_render_error(exc)

    def _result_to_markup(self, result) -> str:
        try:
            from vnalpha.commands.renderers.textual_renderer import result_to_markup

            return result_to_markup(result)
        except Exception:
            return str(result) if result is not None else ""

    # ------------------------------------------------------------------
    # Chat path
    # ------------------------------------------------------------------

    async def _route_chat(self, raw: str) -> None:
        """Dispatch natural-language text to ChatController."""
        self._emit_routed("chat", raw)
        self._set_status_chat()
        try:
            if self._chat_controller is None:
                self._output.show_error("ChatController unavailable.", source="router")
                self._set_status_error("ChatController unavailable")
                return
            await asyncio.to_thread(self._chat_controller.handle_turn, raw)
            self._set_status_ready()
        except Exception as exc:
            self._output.show_error(str(exc), source="chat")
            self._set_status_error(str(exc))
            self._capture_render_error(exc)

    # ------------------------------------------------------------------
    # Plan control
    # ------------------------------------------------------------------

    def _has_pending_plan(self) -> bool:
        return (
            self._chat_controller is not None
            and getattr(self._chat_controller, "_pending_plan", None) is not None
        )

    def _handle_approve(self) -> None:
        self._emit_routed("approve", "/approve")
        if self._chat_controller is not None:
            try:
                self._chat_controller.approve_pending_plan()
            except Exception as exc:
                self._output.show_error(str(exc), source="approve")

    def _handle_cancel(self) -> None:
        self._emit_routed("cancel", "/cancel")
        if self._chat_controller is not None:
            try:
                self._chat_controller.cancel_pending_plan()
            except Exception as exc:
                self._output.show_error(str(exc), source="cancel")

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------

    def _set_status_routing(self) -> None:
        self._update_status("ROUTING_INPUT", label="Routing…")

    def _set_status_command(self, raw: str) -> None:
        self._update_status("COMMAND_RUNNING", label=raw[:40])

    def _set_status_chat(self) -> None:
        self._update_status("CHAT_THINKING", label="Thinking…")

    def _set_status_ready(self) -> None:
        self._update_status("READY")

    def _set_status_error(self, detail: str) -> None:
        self._update_status("ERROR", detail=detail[:80])

    def _set_status_warning(self, detail: str) -> None:
        self._update_status("WARNING", detail=detail[:80])

    def _update_trace_status(self, event) -> None:
        """Update status bar based on tool trace events."""
        if event.status == "RUNNING":
            self._update_status("TOOL_RUNNING", label=event.tool_name)

    def _update_status(
        self, state_name: str, label: str = "", detail: str = ""
    ) -> None:
        if self._status_bar is None:
            return
        try:
            from vnalpha.tui.runtime_status import RuntimeState, RuntimeStatus

            state = RuntimeState(state_name)
            new_status = RuntimeStatus(state=state, label=label, detail=detail)
            self._status_bar.update_status(new_status)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Observability helpers
    # ------------------------------------------------------------------

    def _emit_routed(self, route_type: str, raw: str) -> None:
        """Emit TUI_COMMAND_ROUTED or TUI_CHAT_ROUTED to audit log."""
        try:
            from vnalpha.observability.audit import log_audit

            event = (
                "TUI_COMMAND_ROUTED" if route_type == "command" else "TUI_CHAT_ROUTED"
            )
            log_audit(
                event, f"route_type={route_type}", module="vnalpha.tui.input_router"
            )
        except Exception:
            pass

    def _capture_render_error(self, exc: Exception) -> None:
        """Emit TUI_RENDER_ERROR to observability."""
        try:
            from vnalpha.observability.errors import capture_exception

            capture_exception(exc)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Busy state
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if self._on_busy_change is not None:
            try:
                self._on_busy_change(busy)
            except Exception:
                pass
