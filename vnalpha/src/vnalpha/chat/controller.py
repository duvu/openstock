"""ChatController — owns all chat orchestration for the vnalpha TUI."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Literal

from vnalpha.chat.errors import (
    ChatErrorKind,
    format_refusal,
    format_runtime_error,
    format_tool_failure,
    error_to_message_type,
)
from vnalpha.chat.events import AssistantStage, AssistantStageEvent, format_stage_event, stage_to_style
from vnalpha.chat.modes import ExecutionMode, format_plan_preview, is_safe_read_only_plan
from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.setup import build_default_registry
from vnalpha.warehouse.migrations import run_migrations

if TYPE_CHECKING:
    from vnalpha.assistant.models import AssistantPlan
    from vnalpha.tools.executor import TraceEvent

CHAT_LOCAL_COMMANDS: frozenset[str] = frozenset(
    {"new", "clear", "context", "plan", "trace", "help"}
)


def _make_connection_factory(path: str | None = None) -> Callable:
    from vnalpha.warehouse.connection import get_connection

    def factory():
        return get_connection(path=path)

    return factory


class ChatController:
    def __init__(
        self,
        *,
        connection_factory: Callable | None = None,
        target_date: str | None = None,
        surface: str = "tui-chat",
        on_message: Callable[[str, str], None],
        on_trace: Callable[["TraceEvent"], None] | None = None,
        chat_session_id: str | None = None,
        execution_mode: ExecutionMode = ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY,
    ) -> None:
        self._connection_factory = connection_factory or _make_connection_factory()
        self._target_date = target_date
        self._surface = surface
        self._on_message = on_message
        self._on_trace = on_trace
        self._chat_session_id = chat_session_id
        self.execution_mode: ExecutionMode = execution_mode
        self._pending_plan: "AssistantPlan | None" = None
        self._pending_plan_turn_context: dict | None = None

    def classify_input(
        self, raw: str
    ) -> Literal["slash_command", "chat_local", "natural_language"]:
        stripped = raw.strip()
        if stripped.startswith("/"):
            first_word = stripped[1:].split()[0] if stripped[1:].split() else ""
            if first_word in CHAT_LOCAL_COMMANDS:
                return "chat_local"
            return "slash_command"
        return "natural_language"

    def handle_turn(self, raw: str) -> str | None:
        try:
            kind = self.classify_input(raw)
            if kind == "slash_command":
                return self.handle_slash_command(raw)
            elif kind == "chat_local":
                self._handle_chat_local(raw)
                return None
            else:
                return self.handle_natural_language(raw)
        except Exception as exc:
            error_text = format_runtime_error(str(exc))
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)
            return error_text

    def handle_slash_command(self, raw: str) -> str | None:
        self._on_message("bold cyan", f"> {raw}")
        conn = self._connection_factory()
        try:
            run_migrations(conn=conn)
            registry = build_default_registry()
            executor = CommandExecutor(
                conn=conn,
                surface=self._surface,
                registry=registry,
                default_date=self._target_date,
            )
            result = executor.execute(raw)
            self._render_command_result(result)
            return None
        except Exception as exc:
            error_text = format_runtime_error(str(exc))
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)
            return error_text
        finally:
            conn.close()

    def handle_natural_language(self, question: str) -> str | None:
        self._on_message("bold cyan", f"You: {question}")
        try:
            self._emit_stage(AssistantStage.CLASSIFYING)
            self._emit_stage(AssistantStage.PLANNING)
            answer, plan = self._run_ask(question, no_execute=True)

            if self.execution_mode == ExecutionMode.PLAN_ONLY:
                self._on_message("dim", format_plan_preview(plan))
                return None

            if self.execution_mode == ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY:
                if is_safe_read_only_plan(plan):
                    _original_on_trace = self._on_trace

                    def _staged_on_trace(event: "TraceEvent") -> None:
                        if _original_on_trace:
                            _original_on_trace(event)
                        elapsed = int(event.duration_ms) if event.duration_ms is not None else None
                        if event.status == "RUNNING":
                            self._emit_stage(AssistantStage.TOOL_START, tool_name=event.tool_name)
                        elif event.status == "SUCCESS":
                            self._emit_stage(AssistantStage.TOOL_SUCCESS, tool_name=event.tool_name, elapsed_ms=elapsed)
                        elif event.status == "FAILED":
                            self._emit_stage(AssistantStage.TOOL_FAILED, tool_name=event.tool_name, elapsed_ms=elapsed)
                            failure_text = format_tool_failure(
                                event.tool_name,
                                f"failed after {elapsed}ms" if elapsed is not None else "failed",
                            )
                            self._persist_error_message(
                                failure_text,
                                ChatErrorKind.TOOL_FAILED,
                                role="error",
                            )

                    self._on_trace = _staged_on_trace
                    try:
                        answer, plan = self._run_ask(question, no_execute=False)
                    finally:
                        self._on_trace = _original_on_trace
                    from vnalpha.assistant.models import AssistantAnswer, RefusalMessage
                    self._emit_stage(AssistantStage.SYNTHESIZING)
                    if isinstance(answer, AssistantAnswer):
                        self._emit_stage(AssistantStage.FINAL, text=answer.summary)
                        self._on_message("bold green", f"Assistant: {answer.summary}")
                    elif isinstance(answer, RefusalMessage):
                        refusal_text = format_refusal(answer.reason)
                        self._on_message("yellow", refusal_text)
                        self._persist_error_message(
                            refusal_text,
                            ChatErrorKind.REFUSAL,
                            role="assistant",
                        )
                        return refusal_text
                    else:
                        self._on_message("yellow", f"Refused: {answer.reason}")
                    return None

            self._pending_plan = plan
            self._pending_plan_turn_context = {"question": question}
            self._on_message("dim", format_plan_preview(plan))
            return None

        except Exception as exc:
            error_text = format_runtime_error(str(exc))
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)
            return error_text

    def approve_pending_plan(self) -> None:
        if self._pending_plan is None:
            return
        ctx = self._pending_plan_turn_context or {}
        question = ctx.get("question", "")
        self._pending_plan = None
        self._pending_plan_turn_context = None
        try:
            answer, _plan = self._run_ask(question, no_execute=False)
            from vnalpha.assistant.models import AssistantAnswer, RefusalMessage
            if isinstance(answer, AssistantAnswer):
                self._on_message("bold green", f"Assistant: {answer.summary}")
            elif isinstance(answer, RefusalMessage):
                refusal_text = format_refusal(answer.reason)
                self._on_message("yellow", refusal_text)
                self._persist_error_message(
                    refusal_text,
                    ChatErrorKind.REFUSAL,
                    role="assistant",
                )
            else:
                self._on_message("yellow", f"Refused: {answer.reason}")
        except Exception as exc:
            error_text = format_runtime_error(str(exc))
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)

    def cancel_pending_plan(self) -> None:
        self._pending_plan = None
        self._pending_plan_turn_context = None
        self._on_message("", "Plan canceled.")

    def _handle_chat_local(self, raw: str) -> None:
        stripped = raw.strip()
        parts = stripped[1:].split() if stripped[1:].split() else []
        cmd = parts[0] if parts else ""
        args = parts[1:]
        result = self.handle_chat_local_command(cmd, args)
        self._on_message("bold", result)

    # ------------------------------------------------------------------
    # Public entry point for chat-local command dispatch
    # ------------------------------------------------------------------

    def handle_chat_local_command(self, cmd: str, args: list[str]) -> str:
        """Dispatch a chat-local command and return the response string."""
        if cmd == "new":
            return self._cmd_new()
        elif cmd == "clear":
            forget = "--forget" in args
            return self._cmd_clear(forget=forget)
        elif cmd == "context":
            return self._cmd_context()
        elif cmd == "plan":
            return self._cmd_plan(args)
        elif cmd == "trace":
            return self._cmd_trace(args)
        elif cmd == "help":
            return self._cmd_help()
        else:
            return f"(unknown chat-local command: /{cmd})"

    # ------------------------------------------------------------------
    # Individual command implementations
    # ------------------------------------------------------------------

    def _cmd_new(self) -> str:
        """Create a new chat session, reset session context, return confirmation."""
        from vnalpha.warehouse.chat_repo import create_chat_session
        from vnalpha.warehouse.migrations import run_migrations

        conn = self._connection_factory()
        try:
            run_migrations(conn=conn)
            new_id = create_chat_session(
                conn,
                surface=self._surface,
                target_date=self._target_date,
            )
            self._chat_session_id = new_id
            self._pending_plan = None
            self._pending_plan_turn_context = None
            return f"New chat session started. (id={new_id[:8]}…)"
        finally:
            conn.close()

    def _cmd_clear(self, *, forget: bool = False) -> str:
        """Clear visible messages for the current session.

        If *forget* is True, messages are permanently deleted.
        If there is no active session, returns a warning.
        """
        if not self._chat_session_id:
            return "No active chat session to clear."

        from vnalpha.warehouse.chat_repo import clear_visible_messages
        from vnalpha.warehouse.migrations import run_migrations

        conn = self._connection_factory()
        try:
            run_migrations(conn=conn)
            count = clear_visible_messages(conn, self._chat_session_id)
            if forget:
                return f"Chat log cleared and {count} message(s) deleted from transcript."
            else:
                return f"Chat log cleared ({count} message(s) removed from view)."
        finally:
            conn.close()

    def _cmd_context(self) -> str:
        """Return a formatted string showing the current ChatContext state."""
        from vnalpha.chat.context import ChatContext

        ctx_fields: list[str] = []
        if self._chat_session_id:
            ctx_fields.append(f"  chat_session_id : {self._chat_session_id}")
        if self._target_date:
            ctx_fields.append(f"  target_date     : {self._target_date}")
        ctx_fields.append(f"  execution_mode  : {self.execution_mode.value}")
        ctx_fields.append(f"  surface         : {self._surface}")
        if self._pending_plan is not None:
            ctx_fields.append("  pending_plan    : yes")
        else:
            ctx_fields.append("  pending_plan    : none")

        if ctx_fields:
            return "Current context:\n" + "\n".join(ctx_fields)
        return "No context set."

    def _cmd_plan(self, args: list[str]) -> str:
        """Toggle or show plan mode (ExecutionMode).

        /plan          → show current mode
        /plan on       → set PLAN_THEN_APPROVE
        /plan off      → set AUTO_EXECUTE_SAFE_READ_ONLY
        /plan only     → set PLAN_ONLY
        """
        if not args:
            return f"Plan mode: {self.execution_mode.value}"

        sub = args[0].lower()
        if sub == "on":
            self.execution_mode = ExecutionMode.PLAN_THEN_APPROVE
            return f"Plan mode set to: {self.execution_mode.value}"
        elif sub == "off":
            self.execution_mode = ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
            return f"Plan mode set to: {self.execution_mode.value}"
        elif sub == "only":
            self.execution_mode = ExecutionMode.PLAN_ONLY
            return f"Plan mode set to: {self.execution_mode.value}"
        else:
            return (
                f"Unknown plan sub-command '{sub}'. "
                "Use: /plan, /plan on, /plan off, /plan only"
            )

    def _cmd_trace(self, args: list[str]) -> str:
        """Show trace timeline for the current chat session."""
        if not self._chat_session_id:
            return "No active chat session — no trace available."

        from vnalpha.warehouse.chat_repo import list_trace_events_for_session
        from vnalpha.warehouse.migrations import run_migrations

        conn = self._connection_factory()
        try:
            run_migrations(conn=conn)
            events = list_trace_events_for_session(conn, self._chat_session_id)
        finally:
            conn.close()

        if not events:
            return "No trace events for current session."

        lines = [f"Trace timeline ({len(events)} event(s)):"]
        for ev in events:
            ts = str(ev.get("created_at", ""))[:19]
            content = ev.get("content", "")
            lines.append(f"  {ts}  {content}")
        return "\n".join(lines)

    def _persist_error_message(
        self,
        content: str,
        kind: "ChatErrorKind",
        role: str = "system",
    ) -> None:
        """Persist an error/refusal/tool-failure message to chat_message if session exists."""
        if self._chat_session_id is None:
            return
        try:
            from vnalpha.warehouse.chat_repo import append_chat_message

            conn = self._connection_factory()
            try:
                run_migrations(conn=conn)
                append_chat_message(
                    conn,
                    chat_session_id=self._chat_session_id,
                    role=role,
                    content=content,
                    message_type=error_to_message_type(kind),
                )
            finally:
                conn.close()
        except Exception:
            # Never let persistence failure crash the UI
            pass

    def _cmd_help(self) -> str:
        """Return formatted help text for all chat-local commands."""
        lines = [
            "Chat-local commands:",
            "  /new              — Start a new chat session",
            "  /clear            — Clear the visible chat log (preserves transcript)",
            "  /clear --forget   — Clear visible log AND delete transcript",
            "  /context          — Show current session context state",
            "  /plan             — Show current execution mode",
            "  /plan on          — Set mode to PLAN_THEN_APPROVE",
            "  /plan off         — Set mode to AUTO_EXECUTE_SAFE_READ_ONLY",
            "  /plan only        — Set mode to PLAN_ONLY",
            "  /trace            — Show tool trace timeline for current session",
            "  /help             — Show this help",
            "",
            "Research slash commands (routed to CommandExecutor):",
            "  /scan             — Scan daily watchlist for candidates",
            "  /filter           — Filter candidate scores by conditions",
            "  /compare          — Compare symbols by score/setup/risk",
            "  /explain          — Explain a symbol from persisted score artifacts",
            "  /quality          — Show data quality status",
            "  /lineage          — Show provider/ingestion/feature/scoring version",
            "  /note             — Create a research note linked to a symbol",
            "  /history          — Show recent research sessions",
        ]
        return "\n".join(lines)

    def _run_ask(self, question: str, *, no_execute: bool = False):
        from vnalpha.assistant.app import AssistantApp
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        app = AssistantApp(conn, surface="tui-chat")
        return app.ask(
            question,
            date=self._target_date,
            no_execute=no_execute,
            on_trace_event=self._on_trace,
        )

    def _emit_stage(
        self,
        stage: AssistantStage,
        text: str = "",
        *,
        tool_name: str | None = None,
        elapsed_ms: int | None = None,
    ) -> None:
        event = AssistantStageEvent(stage=stage, text=text, tool_name=tool_name, elapsed_ms=elapsed_ms)
        self._on_message(stage_to_style(stage), format_stage_event(event))

    def _render_command_result(self, result) -> None:
        if result.status == "FAILED":
            summary = result.summary or "Command failed."
            self._on_message("red", summary)
        elif result.status == "VALIDATION_ERROR":
            summary = result.summary or "Validation error."
            self._on_message("yellow", summary)
        else:
            summary = result.summary or ""
            if summary:
                self._on_message("green", f"{result.title}: {summary}")
            else:
                self._on_message("green", result.title)
            for table in result.tables:
                n = len(table.rows)
                self._on_message("dim", f"  {table.title}: {n} row{{'s' if n != 1 else ''}}")
