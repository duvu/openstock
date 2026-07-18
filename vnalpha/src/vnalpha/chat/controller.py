"""ChatController — owns all chat orchestration for the vnalpha TUI."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Callable, Literal

from vnalpha.assistant.tool_policy import is_approval_required_plan, is_safe_plan
from vnalpha.chat.errors import (
    ChatErrorKind,
    error_to_message_type,
    format_refusal,
    format_runtime_error,
    format_tool_failure,
)
from vnalpha.chat.events import (
    AssistantStage,
    AssistantStageEvent,
    format_stage_event,
    stage_to_style,
)
from vnalpha.chat.modes import ExecutionMode, format_plan_preview
from vnalpha.chat.safety import is_tool_approval_pending_eligible
from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.setup import build_default_registry
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.warehouse import migrations as _chat_schema_migrations

if TYPE_CHECKING:
    from vnalpha.assistant.models import (
        AssistantPlan,
        PreparedAssistantTurn,
        RefusalMessage,
    )
    from vnalpha.tools.executor import TraceEvent

CHAT_LOCAL_COMMANDS: frozenset[str] = frozenset(
    {"clear", "context", "plan", "trace", "help"}
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
        on_assistant_answer: Callable[[object], None] | None = None,
        chat_session_id: str | None = None,
        execution_mode: ExecutionMode = ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS,
    ) -> None:
        self._connection_factory = connection_factory or _make_connection_factory()
        self._target_date = target_date
        self._surface = surface
        self._on_message = on_message
        self._on_trace = self._wrap_trace_with_persistence(on_trace)
        self._on_assistant_answer = on_assistant_answer
        self._chat_session_id = chat_session_id
        self.execution_mode: ExecutionMode = execution_mode
        self._pending_plan: "AssistantPlan | None" = None
        self._pending_plan_turn_context: dict | None = None
        self._pending_prepared_turn: "PreparedAssistantTurn | None" = None
        self._chat_schema_ready: bool = False

    def close(self) -> None:
        if self._chat_session_id:
            from vnalpha.model_routing import DEFAULT_OVERRIDE_STORE

            DEFAULT_OVERRIDE_STORE.clear_override(
                scope="session", session_id=self._chat_session_id
            )

    def _ensure_chat_schema_ready(self) -> bool:
        if self._chat_schema_ready:
            return True

        conn = self._connection_factory()
        try:
            _chat_schema_migrations.run_migrations(conn=conn)
            self._chat_schema_ready = True
            return True
        finally:
            conn.close()

    def _wrap_trace_with_persistence(
        self, original: Callable[["TraceEvent"], None] | None
    ) -> Callable[["TraceEvent"], None] | None:
        def _persisting_trace(event: "TraceEvent") -> None:
            if original:
                original(event)
            if self._chat_session_id:
                try:
                    from vnalpha.warehouse.chat_repo import append_trace_event

                    conn = self._connection_factory()
                    try:
                        self._ensure_chat_schema_ready()
                        append_trace_event(
                            conn,
                            chat_session_id=self._chat_session_id,
                            tool_name=event.tool_name,
                            status=event.status,
                            elapsed_ms=event.duration_ms,
                            tool_trace_id=getattr(event, "tool_trace_id", None),
                        )
                    finally:
                        conn.close()
                except Exception:
                    pass

        return _persisting_trace

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

    def handle_turn(
        self,
        raw: str,
        *,
        workspace_context: str | None = None,
        correlation_id: str | None = None,
    ) -> str | None:
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id(
            parent=correlation_id
        ) if correlation_id else set_correlation_id()
        try:
            kind = self.classify_input(raw)
            if kind == "slash_command":
                return self.handle_slash_command(raw)
            elif kind == "chat_local":
                self._handle_chat_local(raw)
                return None
            else:
                return self.handle_natural_language(
                    raw, workspace_context=workspace_context
                )
        except Exception as exc:
            error_text = format_runtime_error(
                "Assistant request failed. Check logs and retry."
            )
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)
            try:
                from vnalpha.observability.errors import capture_exception

                capture_exception(exc)
            except Exception:  # noqa: BLE001
                pass
            return error_text

    def handle_slash_command(self, raw: str) -> str | None:
        self._persist_message("user", raw, "slash_command")
        self._ensure_chat_schema_ready()
        conn = self._connection_factory()
        try:
            registry = build_default_registry()
            executor = CommandExecutor(
                conn=conn,
                surface=self._surface,
                registry=registry,
                default_date=self._target_date,
            )
            execute_parameters = inspect.signature(executor.execute).parameters
            if self._chat_session_id and "session_scope_id" in execute_parameters:
                result = executor.execute(raw, session_scope_id=self._chat_session_id)
            else:
                result = executor.execute(raw)
            self._render_command_result(result)
            if result.pending_prepared_turn is not None:
                self._pending_prepared_turn = result.pending_prepared_turn
                self._pending_plan = result.pending_prepared_turn.plan
                self._pending_plan_turn_context = {
                    "prepared_turn_id": result.pending_prepared_turn.prepared_turn_id,
                    "correlation_id": set_correlation_id(get_correlation_id()),
                }
            research_session_id = None
            metadata = getattr(result, "metadata", None)
            if metadata and isinstance(metadata, dict):
                research_session_id = metadata.get("research_session_id")
                chat_session_id = metadata.get("chat_session_id")
                if chat_session_id:
                    if (
                        self._chat_session_id
                        and self._chat_session_id != chat_session_id
                    ):
                        from vnalpha.model_routing import DEFAULT_OVERRIDE_STORE

                        DEFAULT_OVERRIDE_STORE.clear_override(
                            scope="session", session_id=self._chat_session_id
                        )
                    self._chat_session_id = chat_session_id
                    self._pending_plan = None
                    self._pending_plan_turn_context = None
                    self._pending_prepared_turn = None
            if result.status == "FAILED":
                self._persist_message(
                    "system", result.summary or "Command failed.", "runtime_error"
                )
            elif result.status == "VALIDATION_ERROR":
                self._persist_message(
                    "system",
                    result.summary or "Validation error.",
                    "validation_error",
                )
            else:
                self._persist_message(
                    "assistant",
                    result.summary or result.title,
                    "slash_command_result",
                    research_session_id=research_session_id,
                )
            return None
        except Exception as exc:
            error_text = format_runtime_error(
                "Assistant request failed. Check logs and retry."
            )
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)
            try:
                from vnalpha.observability.errors import capture_exception

                capture_exception(exc)
            except Exception:  # noqa: BLE001
                pass
            return error_text
        finally:
            conn.close()

    def handle_natural_language(
        self, question: str, *, workspace_context: str | None = None
    ) -> str | None:
        self._persist_message("user", question, "prompt")
        if not self._legacy_run_ask_override():
            return self._handle_prepared_natural_language(
                question, workspace_context=workspace_context
            )
        try:
            from vnalpha.observability.audit import log_audit

            log_audit("CHAT_TURN_STARTED", f"question_chars={len(question)}")
        except Exception:  # noqa: BLE001
            pass
        try:
            self._emit_stage(AssistantStage.CLASSIFYING)
            self._emit_stage(AssistantStage.PLANNING)
            if workspace_context is None:
                answer, plan = self._run_ask(question, no_execute=True)
            else:
                answer, plan = self._run_ask(
                    question, no_execute=True, workspace_context=workspace_context
                )

            from vnalpha.assistant.models import RefusalMessage as _RefusalMessage

            if isinstance(answer, _RefusalMessage):
                self._emit_stage(AssistantStage.FINAL, text=answer.reason)
                refusal_text = format_refusal(answer.reason)
                self._on_message("yellow", refusal_text)
                self._persist_error_message(
                    refusal_text, ChatErrorKind.REFUSAL, role="assistant"
                )
                try:
                    from vnalpha.observability.audit import log_audit

                    log_audit("CHAT_REFUSAL", f"Refusal: {answer.reason[:120]}")
                except Exception:  # noqa: BLE001
                    pass
                return refusal_text

            if plan is None or not is_safe_plan(plan):
                refusal = self._evaluate_plan_permissions(plan) or (
                    "Refused: the plan is not safe for execution."
                )
                self._on_message("yellow", refusal)
                self._persist_error_message(
                    refusal, ChatErrorKind.REFUSAL, role="assistant"
                )
                return refusal

            if self.execution_mode == ExecutionMode.PLAN_ONLY:
                import json as _json

                plan_json_str: str | None = None
                if plan is not None:
                    try:
                        plan_json_str = _json.dumps(
                            [
                                getattr(s, "tool_name", None) or str(s)
                                for s in getattr(plan, "steps", [])
                            ]
                        )
                    except Exception:
                        pass
                self._on_message("dim", format_plan_preview(plan))
                self._persist_message(
                    "assistant",
                    format_plan_preview(plan),
                    "plan_preview",
                    plan_json=plan_json_str,
                )
                return None

            if (
                self.execution_mode == ExecutionMode.PLAN_THEN_APPROVE
                and is_safe_plan(plan)
            ) or (
                is_approval_required_plan(plan)
                and is_tool_approval_pending_eligible(
                    plan.steps[0].tool_name, self.execution_mode
                )
            ):
                self._pending_plan = plan
                self._pending_plan_turn_context = {
                    "question": question,
                    "workspace_context": workspace_context,
                    "correlation_id": set_correlation_id(get_correlation_id()),
                }
                preview_text = format_plan_preview(plan)
                self._on_message("dim", preview_text)
                self._persist_message("assistant", preview_text, "plan_preview")
                return None

            if self.execution_mode == ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS:
                if is_safe_plan(plan):
                    _original_on_trace = self._on_trace

                    def _staged_on_trace(event: "TraceEvent") -> None:
                        if _original_on_trace:
                            _original_on_trace(event)
                        elapsed = (
                            int(event.duration_ms)
                            if event.duration_ms is not None
                            else None
                        )
                        if event.status == "RUNNING":
                            self._emit_stage(
                                AssistantStage.TOOL_START, tool_name=event.tool_name
                            )
                        elif event.status == "SUCCESS":
                            self._emit_stage(
                                AssistantStage.TOOL_SUCCESS,
                                tool_name=event.tool_name,
                                elapsed_ms=elapsed,
                            )
                        elif event.status == "FAILED":
                            self._emit_stage(
                                AssistantStage.TOOL_FAILED,
                                tool_name=event.tool_name,
                                elapsed_ms=elapsed,
                            )
                            failure_text = format_tool_failure(
                                event.tool_name,
                                f"failed after {elapsed}ms"
                                if elapsed is not None
                                else "failed",
                            )
                            self._persist_error_message(
                                failure_text,
                                ChatErrorKind.TOOL_FAILED,
                                role="error",
                            )

                    self._on_trace = _staged_on_trace
                    try:
                        if workspace_context is None:
                            answer, plan = self._run_ask(question, no_execute=False)
                        else:
                            answer, plan = self._run_ask(
                                question,
                                no_execute=False,
                                workspace_context=workspace_context,
                            )
                    finally:
                        self._on_trace = _original_on_trace
                    from vnalpha.assistant.models import AssistantAnswer, RefusalMessage

                    self._emit_stage(AssistantStage.SYNTHESIZING)
                    if isinstance(answer, AssistantAnswer):
                        self._emit_assistant_answer(answer)
                    elif isinstance(answer, RefusalMessage):
                        refusal_text = format_refusal(answer.reason)
                        self._on_message("yellow", refusal_text)
                        self._persist_error_message(
                            refusal_text,
                            ChatErrorKind.REFUSAL,
                            role="assistant",
                        )
                        try:
                            from vnalpha.observability.audit import log_audit

                            log_audit("CHAT_REFUSAL", f"Refusal: {answer.reason[:120]}")
                        except Exception:  # noqa: BLE001
                            pass
                        return refusal_text
                    else:
                        refusal_text = f"Refused: {answer.reason}"
                        self._on_message("yellow", refusal_text)
                        self._persist_error_message(
                            refusal_text, ChatErrorKind.REFUSAL, role="assistant"
                        )
                        try:
                            from vnalpha.observability.audit import log_audit

                            log_audit("CHAT_REFUSAL", refusal_text[:120])
                        except Exception:  # noqa: BLE001
                            pass
                    return None

            return None

        except Exception as exc:
            error_text = format_runtime_error(
                "Assistant request failed. Check logs and retry."
            )
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)
            try:
                from vnalpha.observability.errors import capture_exception

                capture_exception(exc)
            except Exception:  # noqa: BLE001
                pass
            return error_text

    def _evaluate_plan_permissions(self, plan: "AssistantPlan | None") -> str | None:
        if plan is None or not plan.steps:
            return "Refused: the plan has no executable steps."

        if is_safe_plan(plan):
            return None

        from vnalpha.assistant.tool_policy import unsafe_tools_in_plan

        unsafe_tools = unsafe_tools_in_plan(plan)
        if unsafe_tools:
            return f"Refused: tool '{unsafe_tools[0]}' is not allowed by the assistant tool policy."
        return "Refused: the plan is not safe for execution."

    def approve_pending_plan(self) -> None:
        if self._pending_prepared_turn is not None:
            prepared = self._pending_prepared_turn
            ctx = self._pending_plan_turn_context or {}
            originating_correlation_id = ctx.get("correlation_id")
            self._pending_prepared_turn = None
            self._pending_plan = None
            self._pending_plan_turn_context = None
            if isinstance(originating_correlation_id, str):
                set_correlation_id(originating_correlation_id)
            self._persist_message("user", "Approved.", "plan_approval")
            try:
                self._approve_prepared_turn(prepared)
                answer, _plan = self._execute_prepared_turn(prepared)
                self._render_prepared_answer(answer)
            except Exception:
                error_text = format_runtime_error(
                    "Assistant request failed. Check logs and retry."
                )
                self._on_message("red", error_text)
                self._persist_error_message(error_text, ChatErrorKind.RUNTIME)
            return
        if self._pending_plan is None:
            return
        if not is_safe_plan(self._pending_plan):
            refusal = self._evaluate_plan_permissions(self._pending_plan) or (
                "Refused: the plan is not safe for execution."
            )
            self._on_message("yellow", refusal)
            self._persist_error_message(
                refusal, ChatErrorKind.REFUSAL, role="assistant"
            )
            self._pending_plan = None
            self._pending_plan_turn_context = None
            return
        ctx = self._pending_plan_turn_context or {}
        question = ctx.get("question", "")
        workspace_context = ctx.get("workspace_context")
        originating_correlation_id = ctx.get("correlation_id")
        if isinstance(originating_correlation_id, str):
            set_correlation_id(originating_correlation_id)
        self._persist_message("user", "Approved.", "plan_approval")
        try:
            from vnalpha.observability.audit import log_audit

            log_audit("PLAN_APPROVED", "User approved plan")
        except Exception:  # noqa: BLE001
            pass
        self._pending_plan = None
        self._pending_plan_turn_context = None
        try:
            if workspace_context is None:
                answer, _plan = self._run_ask(question, no_execute=False)
            else:
                answer, _plan = self._run_ask(
                    question,
                    no_execute=False,
                    workspace_context=workspace_context,
                )
            from vnalpha.assistant.models import AssistantAnswer, RefusalMessage

            if isinstance(answer, AssistantAnswer):
                self._emit_assistant_answer(answer)
            elif isinstance(answer, RefusalMessage):
                refusal_text = format_refusal(answer.reason)
                self._on_message("yellow", refusal_text)
                self._persist_error_message(
                    refusal_text,
                    ChatErrorKind.REFUSAL,
                    role="assistant",
                )
            else:
                refusal_text = f"Refused: {answer.reason}"
                self._on_message("yellow", refusal_text)
                self._persist_error_message(
                    refusal_text, ChatErrorKind.REFUSAL, role="assistant"
                )
        except Exception:
            error_text = format_runtime_error(
                "Assistant request failed. Check logs and retry."
            )
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)

    def cancel_pending_plan(self) -> None:
        if self._pending_prepared_turn is not None:
            prepared = self._pending_prepared_turn
            self._pending_prepared_turn = None
            self._pending_plan = None
            self._pending_plan_turn_context = None
            try:
                from vnalpha.assistant.app import AssistantApp

                conn = self._connection_factory()
                try:
                    self._ensure_chat_schema_ready()
                    AssistantApp(conn, surface=self._surface).cancel_prepared(prepared)
                finally:
                    conn.close()
            except Exception:
                pass
            self._persist_message("user", "Cancelled.", "plan_cancel")
            self._on_message("", "Plan canceled.")
            return
        if self._pending_plan is not None:
            self._persist_message("user", "Cancelled.", "plan_cancel")
            try:
                from vnalpha.observability.audit import log_audit

                log_audit("PLAN_CANCELLED", "User cancelled plan")
            except Exception:  # noqa: BLE001
                pass
        self._pending_plan = None
        self._pending_plan_turn_context = None
        self._on_message("", "Plan canceled.")

    def _handle_chat_local(self, raw: str) -> None:
        stripped = raw.strip()
        parts = stripped[1:].split() if stripped[1:].split() else []
        cmd = parts[0] if parts else ""
        args = parts[1:]
        self._persist_message("user", raw, "chat_local_command")
        result = self.handle_chat_local_command(cmd, args)
        self._on_message("bold", result)
        self._persist_message("system", result, "chat_local_command_result")

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
        from vnalpha.warehouse.chat_repo import create_chat_session

        conn = self._connection_factory()
        try:
            self._ensure_chat_schema_ready()
            new_id = create_chat_session(
                conn,
                surface=self._surface,
                target_date=self._target_date,
            )
            self._chat_session_id = new_id
            self._pending_plan = None
            self._pending_plan_turn_context = None
            self._pending_prepared_turn = None
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

        conn = self._connection_factory()
        try:
            self._ensure_chat_schema_ready()
            count = clear_visible_messages(conn, self._chat_session_id, forget=forget)
            if forget:
                return (
                    f"Chat log cleared and {count} message(s) deleted from transcript."
                )
            else:
                return f"Chat log cleared ({count} message(s) removed from view)."
        finally:
            conn.close()

    def _cmd_context(self) -> str:
        """Return a formatted string showing the current ChatContext state."""

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

        conn = self._connection_factory()
        try:
            self._ensure_chat_schema_ready()
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

    def _persist_message(
        self,
        role: str,
        content: str,
        message_type: str = "plain_text",
        *,
        plan_json: str | None = None,
        research_session_id: str | None = None,
    ) -> None:
        if self._chat_session_id is None:
            return
        try:
            from vnalpha.warehouse.chat_repo import append_chat_message

            conn = self._connection_factory()
            try:
                self._ensure_chat_schema_ready()
                append_chat_message(
                    conn,
                    chat_session_id=self._chat_session_id,
                    role=role,
                    content=content,
                    message_type=message_type,
                    plan_json=plan_json,
                    research_session_id=research_session_id,
                )
            finally:
                conn.close()
        except Exception:
            pass

    def _persist_error_message(
        self,
        content: str,
        kind: "ChatErrorKind",
        role: str = "system",
    ) -> None:
        self._persist_message(role, content, error_to_message_type(kind))

    def _cmd_help(self) -> str:
        """Return formatted help text for all chat-local commands."""
        lines = [
            "Chat-local commands:",
            "  /chat new         — Start a new chat session",
            "  /clear            — Clear the visible chat log (preserves transcript)",
            "  /clear --forget   — Clear visible log AND delete transcript",
            "  /context          — Show current session context state",
            "  /plan             — Show current execution mode",
            "  /plan on          — Set mode to PLAN_THEN_APPROVE",
            "  /plan off         — Set mode to AUTO_EXECUTE_SAFE_READ_ONLY",
            "  /plan only        — Set mode to PLAN_ONLY",
            "  /trace            — Show tool trace timeline for current session",
            "  /new              — Alias for /context new",
            "  /help             — Show this help",
            "",
            "Research slash commands (routed to CommandExecutor):",
            "  /experiment event-study — Run an offline research event study",
            "  /experiment dataset-extension — Probe provider dataset extension capability",
            "  /market-regime    — Show persisted market regime research context",
            "  /sector-strength  — Show persisted sector strength research context",
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

    def _run_ask(
        self,
        question: str,
        *,
        no_execute: bool = False,
        workspace_context: str | None = None,
    ):
        from vnalpha.assistant.app import AssistantApp

        self._ensure_chat_schema_ready()

        conn = self._connection_factory()
        try:
            app = AssistantApp(conn, surface="tui-chat")
            return app.ask(
                question,
                date=self._target_date,
                no_execute=no_execute,
                on_trace_event=self._on_trace,
                workspace_context=workspace_context,
            )
        finally:
            conn.close()

    def _legacy_run_ask_override(self) -> bool:
        return getattr(self._run_ask, "__func__", None) is not ChatController._run_ask

    def _prepare_turn(
        self, question: str, workspace_context: str | None
    ) -> "PreparedAssistantTurn | tuple[RefusalMessage, AssistantPlan]":
        from vnalpha.assistant.app import AssistantApp
        from vnalpha.assistant.models import AssistantRequest

        self._ensure_chat_schema_ready()

        conn = self._connection_factory()
        try:
            app = AssistantApp(conn, surface=self._surface)
            return app.prepare(
                AssistantRequest(
                    current_user_prompt=question,
                    workspace_context=workspace_context,
                    date=self._target_date,
                    routing_session_id=self._chat_session_id,
                )
            )
        finally:
            conn.close()

    def _execute_prepared_turn(self, prepared: "PreparedAssistantTurn"):
        from vnalpha.assistant.app import AssistantApp

        self._ensure_chat_schema_ready()

        conn = self._connection_factory()
        try:
            return AssistantApp(conn, surface=self._surface).execute_prepared(
                prepared,
                on_trace_event=self._on_trace,
                on_synthesizing=lambda: self._emit_stage(AssistantStage.SYNTHESIZING),
            )
        finally:
            conn.close()

    def _approve_prepared_turn(self, prepared: "PreparedAssistantTurn") -> None:
        from vnalpha.sandbox.execution_service import SandboxExecutionService

        self._ensure_chat_schema_ready()

        conn = self._connection_factory()
        try:
            SandboxExecutionService(conn, surface=self._surface).approve_prepared_turn(
                prepared
            )
        finally:
            conn.close()

    def _handle_prepared_natural_language(
        self, question: str, *, workspace_context: str | None
    ) -> str | None:
        try:
            self._emit_stage(AssistantStage.CLASSIFYING)
            self._emit_stage(AssistantStage.PLANNING)
            prepared = self._prepare_turn(question, workspace_context)
            if isinstance(prepared, tuple):
                answer, _plan = prepared
                self._render_prepared_answer(answer)
                return getattr(answer, "reason", None)
            plan = prepared.plan
            if not is_safe_plan(plan) and not is_approval_required_plan(plan):
                refusal = self._evaluate_plan_permissions(plan) or (
                    "Refused: the plan is not safe for execution."
                )
                self._on_message("yellow", refusal)
                self._persist_error_message(
                    refusal, ChatErrorKind.REFUSAL, role="assistant"
                )
                return refusal
            if self.execution_mode == ExecutionMode.PLAN_ONLY:
                self._on_message("dim", format_plan_preview(plan))
                self._persist_message(
                    "assistant", format_plan_preview(plan), "plan_preview"
                )
                return None
            if (
                self.execution_mode == ExecutionMode.PLAN_THEN_APPROVE
                and is_safe_plan(plan)
            ) or (
                is_approval_required_plan(plan)
                and is_tool_approval_pending_eligible(
                    plan.steps[0].tool_name, self.execution_mode
                )
            ):
                self._pending_prepared_turn = prepared
                self._pending_plan = plan
                self._pending_plan_turn_context = {
                    "prepared_turn_id": prepared.prepared_turn_id,
                    "correlation_id": set_correlation_id(get_correlation_id()),
                }
                preview_text = format_plan_preview(plan)
                self._on_message("dim", preview_text)
                self._persist_message("assistant", preview_text, "plan_preview")
                return None
            answer, _plan = self._execute_prepared_turn(prepared)
            self._render_prepared_answer(answer)
            return None
        except Exception:
            error_text = format_runtime_error(
                "Assistant request failed. Check logs and retry."
            )
            self._on_message("red", error_text)
            self._persist_error_message(error_text, ChatErrorKind.RUNTIME)
            return error_text

    def _render_prepared_answer(self, answer) -> None:
        from vnalpha.assistant.models import AssistantAnswer, RefusalMessage

        if isinstance(answer, AssistantAnswer):
            self._emit_assistant_answer(answer)
        elif isinstance(answer, RefusalMessage):
            refusal_text = format_refusal(answer.reason)
            self._on_message("yellow", refusal_text)
            self._persist_error_message(
                refusal_text, ChatErrorKind.REFUSAL, role="assistant"
            )
        else:
            refusal_text = f"Refused: {answer.reason}"
            self._on_message("yellow", refusal_text)
            self._persist_error_message(
                refusal_text, ChatErrorKind.REFUSAL, role="assistant"
            )

    def _emit_stage(
        self,
        stage: AssistantStage,
        text: str = "",
        *,
        tool_name: str | None = None,
        elapsed_ms: int | None = None,
    ) -> None:
        event = AssistantStageEvent(
            stage=stage, text=text, tool_name=tool_name, elapsed_ms=elapsed_ms
        )
        self._on_message(stage_to_style(stage), format_stage_event(event))

    def _emit_assistant_answer(self, answer: object) -> None:
        from vnalpha.assistant.models import AssistantAnswer

        if not isinstance(answer, AssistantAnswer):
            return

        self._persist_message("assistant", answer.summary, "answer")

        if self._on_assistant_answer is not None:
            self._emit_stage(AssistantStage.FINAL, text="complete")
            self._on_assistant_answer(self._build_assistant_answer_message(answer))
            return

        self._emit_stage(AssistantStage.FINAL, text=answer.summary)
        self._on_message("bold green", f"Assistant: {answer.summary}")

    def _build_assistant_answer_message(self, answer: object) -> "object":
        from vnalpha.tui.models.conversation import AssistantAnswerMessage

        return AssistantAnswerMessage(
            text=answer.summary,
            summary=answer.summary,
            basis=getattr(answer, "basis", ""),
            risks_caveats=getattr(answer, "risks_caveats", ""),
            missing_data=list(getattr(answer, "missing_data", [])),
            grounded_source_refs=list(getattr(answer, "grounded_source_refs", [])),
            claim_source_refs=dict(getattr(answer, "claim_source_refs", {})),
            research_metadata=getattr(answer, "research_metadata", None),
            tool_trace_summary=getattr(answer, "tool_trace_summary", ""),
        )

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
                self._on_message(
                    "dim", f"  {table.title}: {n} row{{'s' if n != 1 else ''}}"
                )
