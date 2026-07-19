"""vnalpha TUI application — opencode-like chat-first workspace."""
# allow: SIZE_OK — Textual application lifecycle is the owned TUI composition boundary.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from vnalpha.core.dates import resolve_date
from vnalpha.tui.responsive_layout import ResponsiveLayoutController

if TYPE_CHECKING:
    from vnalpha.tui.clipboard import ClipboardPort
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
    from textual.containers import Vertical
    from textual.events import Resize
    from textual.widgets import Static

    from vnalpha.tui.clipboard import TextualClipboardPort
    from vnalpha.tui.widgets.composer_input import ComposerInput
    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.tui.widgets.status_bar import StatusBar

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class VnAlphaApp(App):
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
            layout: vertical;
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
            Binding("ctrl+o", "open_artifact_detail", "Artifact detail", show=False),
            Binding("ctrl+b", "artifact_back", "Artifact back", show=False),
            Binding("ctrl+y", "copy_result", "Copy result", show=False),
            Binding("ctrl+s", "save_artifact_note", "Artifact note", show=False),
            Binding(
                "ctrl+r",
                "route_artifact_to_assistant",
                "Artifact assistant",
                show=False,
            ),
            Binding("escape", "cancel_pending_plan", "Cancel plan", show=False),
            Binding("f12", "toggle_log_viewer", "Log Viewer", show=False),
            Binding(
                "pageup",
                "transcript_page_up",
                "Transcript page up",
                show=False,
                priority=True,
            ),
            Binding(
                "pagedown",
                "transcript_page_down",
                "Transcript page down",
                show=False,
                priority=True,
            ),
            Binding(
                "home",
                "transcript_home",
                "Transcript start",
                show=False,
                priority=True,
            ),
            Binding(
                "end",
                "transcript_end",
                "Transcript end",
                show=False,
                priority=True,
            ),
        ]

        def __init__(
            self,
            date: Optional[str] = None,
            logging_warning: str | None = None,
            clipboard: ClipboardPort | None = None,
            **kwargs,
        ):
            _load_dotenv()
            super().__init__(**kwargs)
            self.target_date: str = resolve_date(date)
            self.target_date_is_implicit = (
                date is None or date.strip().lower() == "today"
            )
            self._router = None
            self._workspace: WorkspaceState | None = None
            self._layout_controller = ResponsiveLayoutController()
            self._logging_warning = logging_warning
            self._clipboard = clipboard or TextualClipboardPort(self.copy_to_clipboard)
            self._debug_drawer_open = False

        def compose(self) -> ComposeResult:
            """Yield status, responsive main body, composer, and footer hint."""
            yield StatusBar(id="status-bar")
            with Vertical(id="main-body"):
                with Vertical(id="output-column"):
                    yield OutputStream(id="output-stream")
                yield DebugLogDrawer(id="debug-log-drawer")
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
            if self._debug_drawer_open:
                self.action_toggle_log_viewer()
                return
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
            try:
                self._debug_drawer_open = not self._debug_drawer_open
                self._apply_responsive_layout()
                self._ensure_composer_focus()
                _emit_audit_event(
                    "TUI_DEBUG_LOG_DRAWER_TOGGLED",
                    f"visible={self._debug_drawer_open}",
                )
            except Exception:
                pass

        def action_clear_stream(self) -> None:
            """Clear the visible OutputStream."""
            try:
                self.query_one("#output-stream", OutputStream).clear_transcript()
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

        def action_copy_result(self) -> None:
            if self._router is not None:
                self._router.copy_target("result")

        def action_transcript_page_up(self) -> None:
            if self._debug_drawer_open:
                self.query_one("#debug-log-drawer", DebugLogDrawer).page_up()
            else:
                self.query_one("#output-stream", OutputStream).page_up()
            self._ensure_composer_focus()

        def action_transcript_page_down(self) -> None:
            if self._debug_drawer_open:
                self.query_one("#debug-log-drawer", DebugLogDrawer).page_down()
            else:
                self.query_one("#output-stream", OutputStream).page_down()
            self._ensure_composer_focus()

        def action_transcript_home(self) -> None:
            if self._debug_drawer_open:
                self.query_one("#debug-log-drawer", DebugLogDrawer).home()
            else:
                self.query_one("#output-stream", OutputStream).home()
            self._ensure_composer_focus()

        def action_transcript_end(self) -> None:
            if self._debug_drawer_open:
                self.query_one("#debug-log-drawer", DebugLogDrawer).end()
            else:
                self.query_one("#output-stream", OutputStream).end()
            self._ensure_composer_focus()

        def action_save_artifact_note(self) -> None:
            self._prefill_from_artifact("note")

        def action_route_artifact_to_assistant(self) -> None:
            self._prefill_from_artifact("assistant")

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
            log_drawer = self.query_one("#debug-log-drawer", DebugLogDrawer)

            def _on_busy(busy: bool) -> None:
                try:
                    composer = self.query_one("#composer-input", ComposerInput)
                    composer.set_disabled(busy)
                except Exception:
                    pass

            self._router = TuiInputRouter(
                output_stream=output,
                target_date=self.target_date,
                target_date_is_implicit=self.target_date_is_implicit,
                on_busy_change=_on_busy,
                status_bar=status_bar,
                workspace=self._workspace,
                on_workspace_change=self._on_workspace_change,
                ui_dispatcher=self.call_from_thread,
                clipboard=self._clipboard,
                log_text_provider=log_drawer.filtered_plain_text,
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
                return f"{workspace_hint} · Enter submit · F12 logs · /help"
            if self._current_width() < 120:
                return f"{workspace_hint} · Enter · PgUp/Dn · Ctrl+Y · F12 logs · /help"
            if self._current_width() < 140:
                return (
                    f"{workspace_hint} · Enter submit · PgUp/Dn scroll · "
                    "Ctrl+Y result · F12 logs · /help"
                )
            return (
                f"{workspace_hint} · Enter submit · ↑/↓ history · PgUp/Dn scroll · "
                "Ctrl+L clear · Ctrl+Y result · F12 logs · /help"
            )

        def _apply_responsive_layout(self) -> None:
            composer = self.query_one("#composer-input", ComposerInput)
            footer = self.query_one("#footer-hint", Static)
            drawer = self.query_one("#debug-log-drawer", DebugLogDrawer)
            output = self.query_one("#output-stream", OutputStream)
            stick_to_end = output.is_at_end()
            composer.set_suggestion_limit(
                self._layout_controller.suggestion_limit(self._current_height())
            )
            footer.display = self._layout_controller.should_show_footer(
                self._current_height()
            )
            drawer.display = self._debug_drawer_open
            drawer.styles.height = (
                self._layout_controller.debug_drawer_height(self._current_height())
                if self._debug_drawer_open
                else 0
            )
            self.call_after_refresh(output.reflow, stick_to_end=stick_to_end)
            self._refresh_footer_hint()

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
            clipboard: ClipboardPort | None = None,
            **kwargs,
        ):
            del logging_warning, clipboard
            self.target_date: str = resolve_date(date)
            self.target_date_is_implicit = (
                date is None or date.strip().lower() == "today"
            )

        def run(self) -> None:
            raise ImportError("textual is required for the TUI")
