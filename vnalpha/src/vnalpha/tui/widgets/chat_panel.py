"""Persistent ChatPanel widget — always-visible chat + command interface for vnalpha TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnalpha.tools.executor import TraceEvent


def _capture_exception(exc: Exception) -> None:
    try:
        from vnalpha.observability.errors import capture_exception

        capture_exception(exc)
    except Exception:
        pass


try:
    from rich.text import Text
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.widget import Widget
    from textual.widgets import Input, RichLog

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class ChatPanel(Widget):
        """
        Persistent split-pane chat widget.

        Layout (compose):
            RichLog  – scrollable history + tool-trace stream  (expands)
            Input    – always-visible input bar                 (fixed)

        Height: 30% of terminal, with a round $accent border.

        All orchestration is delegated to ChatController. ChatPanel is a
        view/controller adapter only.
        """

        DEFAULT_CSS = """
        ChatPanel {
            height: 30%;
            border: round $accent;
            layout: vertical;
        }
        ChatPanel > RichLog {
            height: 1fr;
        }
        ChatPanel > Input {
            height: 3;
        }
        """

        BINDINGS = [
            Binding("ctrl+backslash", "toggle_panel", "Toggle chat", show=False),
            Binding("ctrl+slash", "focus_input", "Focus chat", show=False),
        ]

        def __init__(
            self,
            conn=None,
            target_date: str | None = None,
            *,
            target_date_is_implicit: bool = False,
            **kwargs,
        ) -> None:
            super().__init__(**kwargs)
            self._conn = conn
            self._target_date = target_date
            self._target_date_is_implicit = target_date_is_implicit
            self._busy = False
            self._chat_controller = None
            self._session_bootstrap_failed = False
            self._setup_controller()

        def _bootstrap_session(self) -> str | None:
            try:
                from vnalpha.warehouse.chat_repo import (
                    get_or_create_active_chat_session,
                )
                from vnalpha.warehouse.connection import get_connection
                from vnalpha.warehouse.migrations import run_migrations

                conn = get_connection()
                try:
                    run_migrations(conn=conn)
                    return get_or_create_active_chat_session(
                        conn,
                        surface="tui-chat",
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
                    self.post_message_text(text, style=style)

                def _on_trace(event: "TraceEvent") -> None:
                    self.post_trace_event(event)

                self._chat_controller = ChatController(
                    target_date=self._target_date,
                    target_date_is_implicit=self._target_date_is_implicit,
                    on_message=_on_message,
                    on_trace=_on_trace,
                    chat_session_id=session_id,
                )
                if session_id is None:
                    self._session_bootstrap_failed = True
            except Exception:
                self._chat_controller = None

        def compose(self) -> ComposeResult:
            yield RichLog(id="chat-log", markup=True, wrap=True)
            yield Input(placeholder="Ask or /command ...", id="chat-input")

        def on_mount(self) -> None:
            if self._session_bootstrap_failed:
                self.post_message_text(
                    "⚠ Chat session bootstrap failed — history will not persist.",
                    style="yellow",
                )

        def post_message_text(self, text: str, style: str = "") -> None:
            """Append styled text to the chat log."""
            log = self.query_one("#chat-log", RichLog)
            log.write(Text(text, style=style or None))

        def post_trace_event(self, event: "TraceEvent") -> None:
            """Render a TraceEvent into the chat log."""
            log = self.query_one("#chat-log", RichLog)
            if event.status == "RUNNING":
                log.write(Text(f"⟳ {event.tool_name} RUNNING…", style="dim"))
            elif event.status == "SUCCESS":
                ms = (
                    f"{event.duration_ms:.0f}ms"
                    if event.duration_ms is not None
                    else ""
                )
                log.write(Text(f"✓ {event.tool_name} SUCCESS {ms}", style="green"))
            else:
                ms = (
                    f"{event.duration_ms:.0f}ms"
                    if event.duration_ms is not None
                    else ""
                )
                log.write(Text(f"✗ {event.tool_name} FAILED {ms}", style="red"))

        def on_input_submitted(self, event: Input.Submitted) -> None:
            raw = event.value.strip()
            if not raw:
                return
            event.input.clear()
            if self._busy:
                self.post_message_text(
                    "⚠ Still processing, please wait…",
                    style="yellow",
                )
                return
            if self._chat_controller is not None:
                self.run_worker(self._dispatch_via_controller(raw), exclusive=True)
            else:
                self.post_message_text("Chat controller unavailable.", style="red")

        async def _dispatch_via_controller(self, raw: str) -> None:
            """Delegate input handling to ChatController asynchronously."""
            import asyncio

            self._set_busy(True)
            try:
                await asyncio.to_thread(self._chat_controller.handle_turn, raw)
            except Exception as exc:
                _capture_exception(exc)
                self.post_message_text(
                    "Assistant request failed. Check logs and retry.",
                    style="red",
                )
            finally:
                self._set_busy(False)

        def action_approve_plan(self) -> None:
            """Approve the pending plan via ChatController."""
            if self._chat_controller is not None:
                try:
                    self._chat_controller.approve_pending_plan()
                except Exception as exc:
                    _capture_exception(exc)
                    self.post_message_text(
                        "Plan approval failed. Check logs and retry.",
                        style="red",
                    )

        def action_cancel_plan(self) -> None:
            """Cancel the pending plan via ChatController."""
            if self._chat_controller is not None:
                try:
                    self._chat_controller.cancel_pending_plan()
                except Exception as exc:
                    _capture_exception(exc)
                    self.post_message_text(
                        "Plan cancellation failed. Check logs and retry.",
                        style="red",
                    )

        def action_toggle_panel(self) -> None:
            """Toggle the chat panel visibility."""
            self.display = not self.display

        def action_focus_input(self) -> None:
            """Focus the chat input widget."""
            self.query_one("#chat-input", Input).focus()

        def _set_busy(self, busy: bool) -> None:
            self._busy = busy
            try:
                inp = self.query_one("#chat-input", Input)
                inp.disabled = busy
            except Exception:
                pass

else:

    class ChatPanel:  # type: ignore[no-redef]
        DEFAULT_CSS = ""
        BINDINGS = []

        def __init__(
            self,
            conn=None,
            target_date: str | None = None,
            *,
            target_date_is_implicit: bool = False,
            **kwargs,
        ) -> None:
            self._conn = conn
            self._target_date = target_date
            self._target_date_is_implicit = target_date_is_implicit
            self._chat_controller = None
            self._setup_controller()

        def _bootstrap_session(self) -> str | None:
            try:
                from vnalpha.warehouse.chat_repo import (
                    get_or_create_active_chat_session,
                )
                from vnalpha.warehouse.connection import get_connection
                from vnalpha.warehouse.migrations import run_migrations

                conn = get_connection()
                try:
                    run_migrations(conn=conn)
                    return get_or_create_active_chat_session(
                        conn,
                        surface="tui-chat",
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
                    pass

                self._chat_controller = ChatController(
                    target_date=self._target_date,
                    target_date_is_implicit=self._target_date_is_implicit,
                    on_message=_on_message,
                    chat_session_id=session_id,
                )
            except Exception:
                self._chat_controller = None
