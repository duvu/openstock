"""vnalpha TUI application — opencode-like chat-first workspace."""

from __future__ import annotations

from typing import Optional

from vnalpha.core.dates import resolve_date

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding

    from vnalpha.tui.widgets.composer_input import ComposerInput
    from vnalpha.tui.widgets.output_stream import OutputStream

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class VnAlphaApp(App):
        """
        vnalpha research-discovery TUI — opencode-like chat-first workspace.

        Layout
        ------
        OutputStream   (scrollable, fills remaining terminal height)
        ComposerInput  (fixed 3-row input bar at the bottom)

        Input routing
        -------------
        /clear            → clear visible stream
        /approve|approve  → approve pending plan
        /cancel|cancel    → cancel pending plan
        /<command>        → CommandExecutor.execute()
        plain text        → ChatController.handle_turn()
        """

        CSS_PATH = None  # inline styles only for portability

        CSS = """
        Screen {
            layout: vertical;
        }
        OutputStream {
            height: 1fr;
        }
        ComposerInput {
            height: 3;
        }
        """

        TITLE = "vnalpha | Research Discovery"
        SUB_TITLE = "Vietnamese Market Research Tool"

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("ctrl+l", "clear_stream", "Clear output", show=False),
            Binding("escape", "cancel_pending_plan", "Cancel plan", show=False),
        ]

        def __init__(self, date: Optional[str] = None, **kwargs):
            super().__init__(**kwargs)
            self.target_date: str = resolve_date(date)
            self._router = None

        def compose(self) -> ComposeResult:
            """Yield OutputStream then ComposerInput — single workspace layout."""
            yield OutputStream(id="output-stream")
            yield ComposerInput(id="composer-input")

        def on_mount(self) -> None:
            """Initialise the input router after widgets are mounted."""
            self._setup_router()
            self._emit_tui_started()

        def _setup_router(self) -> None:
            from vnalpha.tui.input_router import TuiInputRouter

            output = self.query_one("#output-stream", OutputStream)

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
            )

        def _emit_tui_started(self) -> None:
            try:
                from vnalpha.observability.audit import log_audit

                log_audit(
                    "TUI_STARTED",
                    "vnalpha tui workspace mounted",
                    module="vnalpha.tui.app",
                )
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Input event handler
        # ------------------------------------------------------------------

        def on_composer_input_composer_submitted(
            self, event: "ComposerInput.ComposerSubmitted"
        ) -> None:
            """Handle text submitted from ComposerInput and route to the handler."""
            self._emit_input_submitted(event.text)
            if self._router is not None:
                self.run_worker(self._router.route(event.text), exclusive=False)

        def _emit_input_submitted(self, text: str) -> None:
            try:
                from vnalpha.observability.audit import log_audit

                log_audit(
                    "TUI_INPUT_SUBMITTED",
                    f"len={len(text)}",
                    module="vnalpha.tui.app",
                )
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Plan control actions
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Stream control actions
        # ------------------------------------------------------------------

        def action_clear_stream(self) -> None:
            """Clear the visible OutputStream."""
            try:
                self.query_one("#output-stream", OutputStream).clear_visible()
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Legacy compat: show_detail still available for external callers
        # ------------------------------------------------------------------

        def show_detail(self, symbol: str) -> None:
            """Render detail for ``symbol`` into the output stream."""
            try:
                output = self.query_one("#output-stream", OutputStream)
                output.show_table_or_markup(f"[bold]Detail:[/bold] {symbol}")
            except Exception:
                pass

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
