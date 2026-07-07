"""Persistent ChatPanel widget — always-visible chat + command interface for vnalpha TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnalpha.tools.executor import TraceEvent

try:
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

        def __init__(self, conn=None, target_date: str | None = None, **kwargs) -> None:
            super().__init__(**kwargs)
            self._conn = conn
            self._target_date = target_date
            self._busy = False
            self._chat_controller = None
            self._setup_controller()

        def _setup_controller(self) -> None:
            """Construct ChatController with a message callback bound to post_message_text."""
            try:
                from vnalpha.chat.controller import ChatController

                def _on_message(style: str, text: str) -> None:
                    self.post_message_text(text, style=style)

                def _on_trace(event: "TraceEvent") -> None:
                    self.post_trace_event(event)

                self._chat_controller = ChatController(
                    target_date=self._target_date,
                    on_message=_on_message,
                    on_trace=_on_trace,
                )
            except Exception:
                self._chat_controller = None

        def compose(self) -> ComposeResult:
            yield RichLog(id="chat-log", markup=True, wrap=True)
            yield Input(placeholder="Ask or /command ...", id="chat-input")

        def post_message_text(self, text: str, style: str = "") -> None:
            """Append styled text to the chat log."""
            log = self.query_one("#chat-log", RichLog)
            if style:
                log.write(f"[{style}]{text}[/{style}]")
            else:
                log.write(text)

        def post_trace_event(self, event: "TraceEvent") -> None:
            """Render a TraceEvent into the chat log."""
            log = self.query_one("#chat-log", RichLog)
            if event.status == "RUNNING":
                log.write(f"[dim]⟳ {event.tool_name} RUNNING…[/dim]")
            elif event.status == "SUCCESS":
                ms = (
                    f"{event.duration_ms:.0f}ms"
                    if event.duration_ms is not None
                    else ""
                )
                log.write(f"[green]✓ {event.tool_name} SUCCESS {ms}[/green]")
            else:
                ms = (
                    f"{event.duration_ms:.0f}ms"
                    if event.duration_ms is not None
                    else ""
                )
                log.write(f"[red]✗ {event.tool_name} FAILED {ms}[/red]")

        def on_input_submitted(self, event: Input.Submitted) -> None:
            raw = event.value.strip()
            if not raw:
                return
            event.input.clear()
            if self._busy:
                self.post_message_text(
                    "[yellow]⚠ Still processing, please wait…[/yellow]"
                )
                return
            if self._chat_controller is not None:
                self.run_worker(self._dispatch_via_controller(raw), exclusive=True)
            else:
                self.post_message_text("[red]Chat controller unavailable.[/red]")

        async def _dispatch_via_controller(self, raw: str) -> None:
            """Delegate input handling to ChatController asynchronously."""
            import asyncio

            self._set_busy(True)
            try:
                await asyncio.to_thread(self._chat_controller.handle_turn, raw)
            except Exception as exc:
                self.post_message_text(f"[red]Error:[/red] {exc}")
            finally:
                self._set_busy(False)

        def action_approve_plan(self) -> None:
            """Approve the pending plan via ChatController."""
            if self._chat_controller is not None:
                try:
                    self._chat_controller.approve_pending_plan()
                except Exception as exc:
                    self.post_message_text(f"[red]Approve error:[/red] {exc}")

        def action_cancel_plan(self) -> None:
            """Cancel the pending plan via ChatController."""
            if self._chat_controller is not None:
                try:
                    self._chat_controller.cancel_pending_plan()
                except Exception as exc:
                    self.post_message_text(f"[red]Cancel error:[/red] {exc}")

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
        """Importable fallback when textual is unavailable."""

        DEFAULT_CSS = ""
        BINDINGS = []

        def __init__(self, conn=None, target_date: str | None = None, **kwargs) -> None:
            self._conn = conn
            self._target_date = target_date
            self._chat_controller = None
