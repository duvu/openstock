"""Persistent ChatPanel widget — always-visible chat + command interface for vnalpha TUI."""

from __future__ import annotations

import asyncio
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


# ---------------------------------------------------------------------------
# Command dispatcher (Section 4)
# ---------------------------------------------------------------------------

# Maps slash command name → (handler_function_name, handler_module)
_VALID_COMMANDS = {
    "scan",
    "filter",
    "quality",
    "score",
    "explain",
    "compare",
    "lineage",
    "note",
    "history",
    "help",
}


def _get_command_registry():
    """Return the default CommandRegistry (lazy import)."""
    from vnalpha.commands.setup import build_default_registry

    return build_default_registry()


def _parse_command(raw_input: str):
    """Parse a slash command string via the existing parser. Returns ParsedCommand or raises."""
    from vnalpha.commands.parser import parse

    return parse(raw_input)


# ---------------------------------------------------------------------------
# ChatPanel
# ---------------------------------------------------------------------------

if _TEXTUAL_AVAILABLE:

    class ChatPanel(Widget):
        """
        Persistent split-pane chat widget.

        Layout (compose):
            RichLog  – scrollable history + tool-trace stream  (expands)
            Input    – always-visible input bar                 (fixed)

        Height: 30% of terminal, with a round $accent border.
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
            # conn + date are optional; if absent the panel is read-only / cosmetic
            self._conn = conn
            self._target_date = target_date
            self._registry = _get_command_registry()
            self._busy = False

        def compose(self) -> ComposeResult:
            yield RichLog(id="chat-log", markup=True, wrap=True)
            yield Input(placeholder="Ask or /command ...", id="chat-input")

        # ------------------------------------------------------------------
        # Public helpers
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Input handling
        # ------------------------------------------------------------------

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
            if raw.startswith("/"):
                self._dispatch_command_sync(raw)
            else:
                self.run_worker(self._dispatch_assistant(raw), exclusive=True)

        # ------------------------------------------------------------------
        # Assistant dispatch (async, runs in worker)
        # ------------------------------------------------------------------

        async def _dispatch_assistant(self, question: str) -> None:
            """Run AssistantApp.ask() in a thread and post the result."""
            self._set_busy(True)
            self.post_message_text(f"[bold cyan]You:[/bold cyan] {question}")

            def _on_trace(evt: "TraceEvent") -> None:
                # Called from worker thread — use call_from_thread to update UI
                self.app.call_from_thread(self.post_trace_event, evt)

            try:
                answer, _plan = await asyncio.to_thread(
                    self._run_ask, question, _on_trace
                )
                from vnalpha.assistant.models import AssistantAnswer

                if isinstance(answer, AssistantAnswer):
                    self.post_message_text(
                        f"[bold green]Assistant:[/bold green] {answer.summary}"
                    )
                else:
                    self.post_message_text(f"[yellow]Refused:[/yellow] {answer.reason}")
            except Exception as exc:
                self.post_message_text(f"[red]Error:[/red] {exc}")
            finally:
                self._set_busy(False)

        def _run_ask(self, question: str, on_trace_event):
            """Synchronous helper for AssistantApp.ask(), called inside to_thread."""
            from vnalpha.assistant.app import AssistantApp
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.migrations import run_migrations

            # Each chat call opens its own connection (DuckDB multi-reader safe)
            conn = get_connection()
            run_migrations(conn=conn)
            app = AssistantApp(conn, surface="tui")
            return app.ask(
                question,
                date=self._target_date,
                on_trace_event=on_trace_event,
            )

        # ------------------------------------------------------------------
        # Command dispatch (sync)
        # ------------------------------------------------------------------

        def _dispatch_command_sync(self, raw_input: str) -> None:
            """Parse and dispatch a slash command; post result to log."""
            from vnalpha.commands.errors import CommandParseError, UnknownCommandError

            self.post_message_text(f"[bold cyan]>[/bold cyan] {raw_input}")

            try:
                parsed = _parse_command(raw_input)
            except CommandParseError as exc:
                self.post_message_text(f"[red]Parse error:[/red] {exc}")
                return

            cmd_name = parsed.command_name
            if cmd_name not in _VALID_COMMANDS:
                valid = ", ".join(sorted(_VALID_COMMANDS))
                self.post_message_text(
                    f"[red]Unknown command '/{cmd_name}'.[/red] Valid commands: {valid}"
                )
                return

            try:
                from vnalpha.tools.executor import TracedLocalToolExecutor
                from vnalpha.tools.setup import build_local_tool_registry

                tool_executor = None
                if self._conn is not None:
                    registry = build_local_tool_registry(self._conn)
                    tool_executor = TracedLocalToolExecutor(
                        self._conn,
                        registry,
                        session_id=None,
                        trace_parent_type="command",
                        trace_event_callback=self.post_trace_event,
                    )

                result = self._registry.execute(
                    parsed,
                    conn=self._conn,
                    tool_executor=tool_executor,
                )
                self._render_command_result(result)
            except UnknownCommandError:
                valid = ", ".join(sorted(_VALID_COMMANDS))
                self.post_message_text(
                    f"[red]Unknown command '/{cmd_name}'.[/red] Valid commands: {valid}"
                )
            except Exception as exc:
                self.post_message_text(f"[red]Command error:[/red] {exc}")

        def _render_command_result(self, result) -> None:
            """Format CommandResult for the chat log."""
            if result.status == "FAILED":
                summary = result.summary or "Command failed."
                self.post_message_text(f"[red]{summary}[/red]")
            elif result.status == "VALIDATION_ERROR":
                summary = result.summary or "Validation error."
                self.post_message_text(f"[yellow]{summary}[/yellow]")
            else:
                summary = result.summary or ""
                if summary:
                    self.post_message_text(f"[green]{result.title}:[/green] {summary}")
                else:
                    self.post_message_text(f"[green]{result.title}[/green]")
                # Show table row counts if present
                for table in result.tables:
                    n = len(table.rows)
                    self.post_message_text(
                        f"[dim]  {table.title}: {n} row{'s' if n != 1 else ''}[/dim]"
                    )

        # ------------------------------------------------------------------
        # Actions / bindings
        # ------------------------------------------------------------------

        def action_toggle_panel(self) -> None:
            """Toggle the chat panel visibility."""
            self.display = not self.display

        def action_focus_input(self) -> None:
            """Focus the chat input widget."""
            self.query_one("#chat-input", Input).focus()

        # ------------------------------------------------------------------
        # Internal helpers
        # ------------------------------------------------------------------

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
