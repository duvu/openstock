"""OutputStream widget — append-only scrollable output stream for the chat-first TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnalpha.tools.executor import TraceEvent

try:
    from rich.console import RenderableType
    from textual.app import ComposeResult
    from textual.widget import Widget
    from textual.widgets import RichLog

    _TEXTUAL_AVAILABLE = True
except ImportError:
    RenderableType = str  # type: ignore[assignment,misc]
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class OutputStream(Widget):
        """
        Append-only scrollable output stream.

        Renders all TUI output (user input echoes, assistant messages, command
        results, tool traces, errors, warnings) into a single scrolling stream.

        All rendering is append-only; call ``clear_visible()`` to clear the
        visible area without touching audit logs or persisted chat history.
        """

        DEFAULT_CSS = """
        OutputStream {
            height: 1fr;
            border: round $surface-darken-1;
        }
        OutputStream > RichLog {
            height: 1fr;
            scrollbar-gutter: stable;
        }
        """

        def compose(self) -> ComposeResult:
            yield RichLog(id="output-log", markup=True, wrap=True, highlight=False)

        def on_mount(self) -> None:
            # The output log is append-only: it must never steal keyboard focus
            # from the composer input, otherwise typing "/" would not reach the
            # Input and the slash-command suggestion list would never appear.
            try:
                self.query_one("#output-log", RichLog).can_focus = False
            except Exception:  # noqa: BLE001
                pass

        # ------------------------------------------------------------------
        # Public rendering methods
        # ------------------------------------------------------------------

        def show_user_input(self, text: str) -> None:
            """Echo the user's raw input back into the stream."""
            self._write(f"[bold cyan]❯ {text}[/bold cyan]")

        def show_assistant_message(self, text: str, style: str | None = None) -> None:
            """Render an assistant message, optionally with a style."""
            if style:
                self._write(f"[{style}]{text}[/{style}]")
            else:
                self._write(text)

        def show_command_result(self, command: str, result: "RenderableType") -> None:
            """Render a command result preceded by the command label."""
            self._write(f"[dim]$ {command}[/dim]")
            self._write(result)
            self._write("")  # spacing after command output

        def show_error(self, message: str, source: str | None = None) -> None:
            """Render an error message, optionally with a source label."""
            src = f" ({source})" if source else ""
            self._write(f"[bold red]✗ Error{src}:[/bold red] {message}")

        def show_warning(self, message: str, source: str | None = None) -> None:
            """Render a warning message, optionally with a source label."""
            src = f" ({source})" if source else ""
            self._write(f"[yellow]⚠ Warning{src}:[/yellow] {message}")

        def show_trace_event(self, event: "TraceEvent") -> None:
            """Render a tool TraceEvent inline with consistent formatting."""
            if event.status == "RUNNING":
                self._write(f"  [dim]⟳ {event.tool_name}…[/dim]")
            elif event.status == "SUCCESS":
                ms = (
                    f" ({event.duration_ms:.0f}ms)"
                    if event.duration_ms is not None
                    else ""
                )
                self._write(f"  [green]✓ {event.tool_name}{ms}[/green]")
            else:
                ms = (
                    f" ({event.duration_ms:.0f}ms)"
                    if event.duration_ms is not None
                    else ""
                )
                self._write(f"  [red]✗ {event.tool_name}{ms}[/red]")

        def show_data_ensure_progress(
            self, step: str, status: str, detail: str = ""
        ) -> None:
            """Show data provisioning progress inline."""
            if status == "running":
                self._write(f"  [dim yellow]⟳ {step}…[/dim yellow]")
            elif status == "done":
                suffix = f" — {detail}" if detail else ""
                self._write(f"  [green]✓ {step}{suffix}[/green]")
            else:
                suffix = f" — {detail}" if detail else ""
                self._write(f"  [red]✗ {step}{suffix}[/red]")

        def show_table_or_markup(self, markup: "RenderableType") -> None:
            """Render arbitrary rich markup or Rich Renderable."""
            self._write(markup)

        def show_repair_bundle(self, path: str, repair_id: str | None = None) -> None:
            """Show that a repair bundle was created."""
            rid = f" [{repair_id}]" if repair_id else ""
            self._write(
                f"[bold green]✓ Repair bundle created{rid}:[/bold green] {path}"
            )

        def show_deploy_status(self, status: str, details: str | None = None) -> None:
            """Show a deploy status line."""
            colour = (
                "green"
                if status.upper() in ("PASSED", "PROMOTED", "SUCCESS")
                else "yellow"
            )
            detail = f" — {details}" if details else ""
            self._write(f"[{colour}]⬡ Deploy: {status}{detail}[/{colour}]")

        def show_section_break(self) -> None:
            """Render a visual separator between logical output sections."""
            self._write("[dim]───────────────────────────────────────[/dim]")

        def clear_visible(self) -> None:
            """Clear the visible stream only. Does NOT delete logs or history."""
            try:
                self.query_one("#output-log", RichLog).clear()
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Internal helpers
        # ------------------------------------------------------------------

        def _write(self, text: "RenderableType") -> None:
            """Append a line or Rich renderable to the RichLog (best-effort)."""
            try:
                self.query_one("#output-log", RichLog).write(text)
            except Exception:
                pass

else:

    class OutputStream:  # type: ignore[no-redef]
        """Importable fallback used when textual is unavailable."""

        DEFAULT_CSS = ""

        def __init__(self, **kwargs) -> None:
            pass

        def show_user_input(self, text: str) -> None:
            pass

        def show_assistant_message(self, text: str, style: str | None = None) -> None:
            pass

        def show_command_result(self, command: str, result: "RenderableType") -> None:
            pass

        def show_error(self, message: str, source: str | None = None) -> None:
            pass

        def show_warning(self, message: str, source: str | None = None) -> None:
            pass

        def show_trace_event(self, event: "TraceEvent") -> None:
            pass

        def show_data_ensure_progress(
            self, step: str, status: str, detail: str = ""
        ) -> None:
            pass

        def show_table_or_markup(self, markup: "RenderableType") -> None:
            pass

        def show_repair_bundle(self, path: str, repair_id: str | None = None) -> None:
            pass

        def show_deploy_status(self, status: str, details: str | None = None) -> None:
            pass

        def show_section_break(self) -> None:
            pass

        def clear_visible(self) -> None:
            pass
