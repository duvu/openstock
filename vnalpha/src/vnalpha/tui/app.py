"""vnalpha TUI application — opencode-like chat-first workspace."""
# allow: SIZE_OK — Textual application lifecycle is the owned TUI composition boundary.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from vnalpha.core.dates import resolve_date
from vnalpha.tui.responsive_layout import ResponsiveLayoutController
from vnalpha.tui.todo_source import (
    CompositeTodoSource,
    FallbackTodoSource,
    WorkspaceTodoSource,
)

if TYPE_CHECKING:
    from vnalpha.tui.widgets.todo_panel import TodoPanel
    from vnalpha.workspace_context.models import WorkspaceResumeSummary, WorkspaceState


def _load_dotenv() -> None:
    """Load .env from the workspace root (best-effort, never raises)."""
    try:
        from dotenv import find_dotenv, load_dotenv

        env_file = find_dotenv(usecwd=True)
        if env_file:
            load_dotenv(env_file, override=False)
    except Exception:  # noqa: BLE001
        pass


def _emit_audit_event(event_name: str, detail: str) -> None:
    """Emit a best-effort audit event for the TUI."""

    try:
        from vnalpha.observability.audit import log_audit

        log_audit(event_name, detail, module="vnalpha.tui.app")
    except Exception:  # noqa: BLE001
        pass


try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.events import Resize
    from textual.widgets import Static

    from vnalpha.tui.widgets.composer_input import ComposerInput
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.tui.widgets.status_bar import StatusBar
    from vnalpha.tui.widgets.todo_panel import TodoPanel

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class VnAlphaApp(App):
        """vnalpha research-discovery TUI with an optional responsive TODO rail."""

        # Focus the composer input on launch so the first keystrokes (e.g. "/")
        # reach the Input and trigger slash-command suggestion rendering instead
        # of being swallowed by the focusable output log.
        AUTO_FOCUS = "#composer-input-field"

        CSS_PATH = None
        CSS = """
        Screen {
            layout: vertical;
            overflow: hidden;
        }
        StatusBar {
            height: 1;
            max-height: 1;
        }
        #main-body {
            height: 1fr;
            width: 100%;
            layout: horizontal;
            min-height: 0;
            overflow: hidden;
        }
        #output-column {
            height: 1fr;
            width: 1fr;
            min-height: 0;
            overflow: hidden;
        }
        OutputStream {
            height: 1fr;
            min-height: 0;
            overflow: hidden;
        }
        ComposerInput {
            height: auto;
            min-height: 3;
            max-height: 16;
        }
        #footer-hint {
            height: 1;
            max-height: 1;
            width: 100%;
            background: $surface-darken-1;
            color: $text-muted;
            padding: 0 1;
        }
        """

        TITLE = "vnalpha | Research Discovery"
        SUB_TITLE = "Vietnamese Market Research Tool"
        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("ctrl+l", "clear_stream", "Clear output", show=False),
            Binding("ctrl+t", "toggle_todo_panel", "TODOs", show=False),
            Binding("ctrl+o", "open_artifact_detail", "Artifact detail", show=False),
            Binding("ctrl+b", "artifact_back", "Artifact back", show=False),
            Binding("ctrl+y", "copy_artifact_id", "Artifact id", show=False),
            Binding("ctrl+s", "save_artifact_note", "Artifact note", show=False),
            Binding(
                "ctrl+r",
                "route_artifact_to_assistant",
                "Artifact assistant",
                show=False,
            ),
            Binding("escape", "cancel_pending_plan", "Cancel plan", show=False),
            Binding("f12", "toggle_log_viewer", "Log Viewer", show=False),
        ]

        def __init__(
            self,
            date: Optional[str] = None,
            logging_warning: str | None = None,
            **kwargs,
        ):
            _load_dotenv()
            super().__init__(**kwargs)
            self.target_date: str = resolve_date(date)
            self._router = None
            self._workspace: WorkspaceState | None = None
            self._layout_controller = ResponsiveLayoutController()
            self._todo_preference: bool | None = None
            self._last_todo_visible: bool | None = None
            self._logging_warning = logging_warning
            self._todo_source = CompositeTodoSource(
                [WorkspaceTodoSource(), FallbackTodoSource()]
            )

        def compose(self) -> ComposeResult:
            """Yield status, responsive main body, composer, and footer hint."""
            yield StatusBar(id="status-bar")
            with Horizontal(id="main-body"):
                with Vertical(id="output-column"):
                    yield OutputStream(id="output-stream")
                yield TodoPanel(source=self._todo_source, id="todo-panel")
            yield ComposerInput(id="composer-input")
            yield Static(self._footer_hint_text(), id="footer-hint")

        def on_mount(self) -> None:
            """Initialise the input router after widgets are mounted."""
            self._start_workspace_lifecycle()
            self._setup_router()
            self._emit_tui_started()
            self._apply_responsive_layout()
            self._ensure_composer_focus()
            if self._logging_warning is not None:
                self.query_one("#output-stream", OutputStream).show_warning(
                    self._logging_warning,
                    source="logging",
                )

        def on_unmount(self) -> None:
            if self._router is not None:
                self._router.close()

        def on_resize(self, event: Resize) -> None:
            """Recompute TODO panel visibility when terminal size changes."""
            del event
            self._apply_responsive_layout()
            self._ensure_composer_focus()

        def on_composer_input_composer_submitted(
            self, event: "ComposerInput.ComposerSubmitted"
        ) -> None:
            """Handle text submitted from ComposerInput and route to the handler."""
            self._emit_input_submitted(event.text)
            if self._router is not None:
                self.run_worker(self._router.route(event.text), exclusive=False)

        def action_cancel_pending_plan(self) -> None:
            """Cancel pending plan via the router's ChatController."""
            if self._router is not None:
                try:
                    self._router._handle_cancel()
                except Exception:
                    pass

        def action_approve_plan(self) -> None:
            """Approve pending plan via the router's ChatController."""
            if self._router is not None:
                try:
                    self._router._handle_approve()
                except Exception:
                    pass

        def action_toggle_log_viewer(self) -> None:
            """Push the LogScreen overlay so users can view live logs."""
            try:
                from vnalpha.tui.screens.log_viewer import LogScreen

                self.push_screen(LogScreen())
            except Exception:
                pass

        def action_clear_stream(self) -> None:
            """Clear the visible OutputStream."""
            try:
                self.query_one("#output-stream", OutputStream).clear_visible()
            except Exception:
                pass

        def action_open_artifact_detail(self) -> None:
            try:
                output = self.query_one("#output-stream", OutputStream)
                opened = output.open_latest_artifact_detail()
                if not opened:
                    output.show_warning(
                        "No artifact detail is available for the latest command.",
                        source="artifact",
                    )
            except Exception:
                pass

        def action_artifact_back(self) -> None:
            try:
                self.query_one("#output-stream", OutputStream).navigate_back()
            except Exception:
                pass

        def action_copy_artifact_id(self) -> None:
            try:
                output = self.query_one("#output-stream", OutputStream)
                artifact_id = output.current_artifact_id()
                if artifact_id:
                    output.show_assistant_message(
                        f"Artifact ID: {artifact_id}", style="dim"
                    )
            except Exception:
                pass

        def action_save_artifact_note(self) -> None:
            self._prefill_from_artifact("note")

        def action_route_artifact_to_assistant(self) -> None:
            self._prefill_from_artifact("assistant")

        def action_toggle_todo_panel(self) -> None:
            """Toggle the TODO side rail on wide terminals only."""
            can_show = self._layout_controller.should_show_todo(
                self._current_width(), None
            )
            if not can_show:
                self._apply_responsive_layout()
                self._ensure_composer_focus()
                return
            self._todo_preference = not self._layout_controller.should_show_todo(
                self._current_width(), self._todo_preference
            )
            self._apply_responsive_layout()
            self._ensure_composer_focus()
            _emit_audit_event(
                "TUI_TODO_PANEL_TOGGLED",
                f"visible={self._todo_preference is not False}",
            )

        def show_detail(self, symbol: str) -> None:
            """Render detail for ``symbol`` into the output stream."""
            try:
                output = self.query_one("#output-stream", OutputStream)
                output.show_table_or_markup(f"[bold]Detail:[/bold] {symbol}")
            except Exception:
                pass

        def _setup_router(self) -> None:
            from vnalpha.tui.input_router import TuiInputRouter

            output = self.query_one("#output-stream", OutputStream)
            status_bar = self.query_one("#status-bar", StatusBar)

            def _on_busy(busy: bool) -> None:
                try:
                    composer = self.query_one("#composer-input", ComposerInput)
                    composer.set_disabled(busy)
                except Exception:
                    pass

            self._router = TuiInputRouter(
                output_stream=output,
                target_date=self.target_date,
                on_busy_change=_on_busy,
                status_bar=status_bar,
                workspace=self._workspace,
                on_workspace_change=self._on_workspace_change,
                ui_dispatcher=self.call_from_thread,
            )

        def _start_workspace_lifecycle(self) -> None:
            from vnalpha.tui.workspace_presentation import (
                initialize_workspace,
            )

            self._workspace, summary = initialize_workspace()
            self._render_workspace_resume(summary)

        def _on_workspace_change(self, workspace: "WorkspaceState") -> None:
            from vnalpha.tui.workspace_presentation import resume_summary_for

            self._workspace = workspace
            self._render_workspace_resume(resume_summary_for(workspace))
            self._refresh_todo_panel()

        def _render_workspace_resume(self, summary: "WorkspaceResumeSummary") -> None:
            from vnalpha.tui.workspace_presentation import render_workspace_resume

            status_bar = self.query_one("#status-bar", StatusBar)
            output = self.query_one("#output-stream", OutputStream)
            render_workspace_resume(summary, status_bar, output)
            self._refresh_footer_hint()

        def _emit_tui_started(self) -> None:
            _emit_audit_event("TUI_STARTED", "vnalpha tui workspace mounted")

        def _emit_input_submitted(self, text: str) -> None:
            _emit_audit_event("TUI_INPUT_SUBMITTED", f"len={len(text)}")

        def _current_width(self) -> int:
            return self.size.width if self.size.width > 0 else 120

        def _current_height(self) -> int:
            return self.size.height if self.size.height > 0 else 30

        def _footer_hint_text(self) -> str:
            workspace_hint = (
                f"ws={self._workspace.workspace_id} · {self._workspace.mode}"
                if self._workspace is not None
                else "ws=loading"
            )
            if self._current_width() < 100:
                return f"{workspace_hint} · Enter submit · /help · Esc cancel"
            if self._layout_controller.should_show_todo(
                self._current_width(), self._todo_preference
            ):
                return (
                    f"{workspace_hint} · Enter submit · ↑/↓ history · Ctrl+L clear · "
                    "Ctrl+T TODOs · /help · Esc cancel"
                )
            return (
                f"{workspace_hint} · Enter submit · ↑/↓ history · Ctrl+L clear · "
                "TODOs hidden · /help · Esc cancel"
            )

        def _apply_responsive_layout(self) -> None:
            panel = self.query_one("#todo-panel", TodoPanel)
            composer = self.query_one("#composer-input", ComposerInput)
            footer = self.query_one("#footer-hint", Static)
            show_panel = self._layout_controller.should_show_todo(
                self._current_width(), self._todo_preference
            )
            composer.set_suggestion_limit(
                self._layout_controller.suggestion_limit(self._current_height())
            )
            footer.display = self._layout_controller.should_show_footer(
                self._current_height()
            )
            panel.display = show_panel
            if show_panel:
                panel.styles.width = self._layout_controller.todo_width(
                    self._current_width()
                )
                panel.refresh_items()
            if self._last_todo_visible != show_panel:
                self._emit_todo_visibility(
                    "TUI_TODO_PANEL_VISIBLE" if show_panel else "TUI_TODO_PANEL_HIDDEN"
                )
            self._refresh_footer_hint()

        def _refresh_todo_panel(self) -> None:
            try:
                self.query_one("#todo-panel", TodoPanel).refresh_items()
            except Exception:
                pass

        def _refresh_footer_hint(self) -> None:
            try:
                self.query_one("#footer-hint", Static).update(self._footer_hint_text())
            except Exception:
                pass

        def _ensure_composer_focus(self) -> None:
            self.call_after_refresh(self._focus_composer)

        def _focus_composer(self) -> None:
            try:
                self.query_one("#composer-input", ComposerInput).focus_input()
            except Exception:
                pass

        def _prefill_from_artifact(self, mode: str) -> None:
            try:
                output = self.query_one("#output-stream", OutputStream)
                composer = self.query_one("#composer-input", ComposerInput)
                if mode == "note":
                    value = output.note_command_for_current_artifact()
                else:
                    value = output.assistant_prompt_for_current_artifact()
                if value:
                    composer.set_text(value)
                    composer.focus_input()
            except Exception:
                pass

        def _emit_todo_visibility(self, event_name: str) -> None:
            self._last_todo_visible = event_name == "TUI_TODO_PANEL_VISIBLE"
            _emit_audit_event(event_name, f"width={self._current_width()}")

else:

    class VnAlphaApp:  # type: ignore[no-redef]
        """Importable fallback used when textual is unavailable."""

        TITLE = "vnalpha | Research Discovery"
        SUB_TITLE = "Vietnamese Market Research Tool"
        BINDINGS = []

        def __init__(
            self,
            date: Optional[str] = None,
            logging_warning: str | None = None,
            **kwargs,
        ):
            del logging_warning
            self.target_date: str = resolve_date(date)

        def run(self) -> None:
            raise ImportError("textual is required for the TUI")
