"""vnalpha TUI application — opencode-like chat-first workspace."""

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

        CSS_PATH = None
        CSS = """
        Screen {
            layout: vertical;
        }
        StatusBar {
            height: 1;
            max-height: 1;
        }
        #main-body {
            height: 1fr;
            width: 100%;
            layout: horizontal;
        }
        #output-column {
            height: 1fr;
            width: 1fr;
        }
        OutputStream {
            height: 1fr;
            min-height: 5;
        }
        ComposerInput {
            height: 3;
            min-height: 3;
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
            Binding("escape", "cancel_pending_plan", "Cancel plan", show=False),
            Binding("f12", "toggle_log_viewer", "Log Viewer", show=False),
        ]

        def __init__(self, date: Optional[str] = None, **kwargs):
            _load_dotenv()
            super().__init__(**kwargs)
            self.target_date: str = resolve_date(date)
            self._router = None
            self._layout_controller = ResponsiveLayoutController()
            self._todo_preference: bool | None = None
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
            self._setup_router()
            self._emit_tui_started()
            self._apply_responsive_layout()
            self._ensure_composer_focus()

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
                self._refresh_todo_panel()

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

        def action_toggle_todo_panel(self) -> None:
            """Toggle the TODO side rail on wide terminals only."""
            can_show = self._layout_controller.should_show_todo(self._current_width(), None)
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
            )

        def _emit_tui_started(self) -> None:
            _emit_audit_event("TUI_STARTED", "vnalpha tui workspace mounted")

        def _emit_input_submitted(self, text: str) -> None:
            _emit_audit_event("TUI_INPUT_SUBMITTED", f"len={len(text)}")

        def _current_width(self) -> int:
            return self.size.width if self.size.width > 0 else 120

        def _footer_hint_text(self) -> str:
            if self._layout_controller.should_show_todo(
                self._current_width(), self._todo_preference
            ):
                return (
                    "Enter submit · ↑/↓ history · Ctrl+L clear · Ctrl+T TODOs · "
                    "F12 logs · /help commands · Esc cancel"
                )
            return (
                "Enter submit · ↑/↓ history · Ctrl+L clear · TODOs hidden: narrow terminal · "
                "F12 logs · /help commands · Esc cancel"
            )

        def _apply_responsive_layout(self) -> None:
            panel = self.query_one("#todo-panel", TodoPanel)
            show_panel = self._layout_controller.should_show_todo(
                self._current_width(), self._todo_preference
            )
            panel.display = show_panel
            if show_panel:
                panel.styles.width = self._layout_controller.todo_width(
                    self._current_width()
                )
                panel.refresh_items()
                self._emit_todo_visibility("TUI_TODO_PANEL_VISIBLE")
            else:
                self._emit_todo_visibility("TUI_TODO_PANEL_HIDDEN")
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

        def _emit_todo_visibility(self, event_name: str) -> None:
            _emit_audit_event(event_name, f"width={self._current_width()}")

else:

    class VnAlphaApp:  # type: ignore[no-redef]
        """Importable fallback used when textual is unavailable."""

        TITLE = "vnalpha | Research Discovery"
        SUB_TITLE = "Vietnamese Market Research Tool"
        BINDINGS = []

        def __init__(self, date: Optional[str] = None, **kwargs):
            self.target_date: str = resolve_date(date)

        def run(self) -> None:
            raise ImportError("textual is required for the TUI")
