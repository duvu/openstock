"""ComposerInput widget — single input bar with history for the chat-first TUI workspace."""

from __future__ import annotations

import os

from vnalpha.core.logging import get_logger
from vnalpha.tui.input_history import InputHistory

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.message import Message
    from textual.widget import Widget
    from textual.widgets import Input, Static

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:
    _TUI_SUGGEST_DEBUG = os.getenv("VNALPHA_TUI_SUGGEST_DEBUG", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    class ComposerInput(Widget):
        """
        Single-input composer bar for the chat-first TUI workspace.

        Owns exactly one Textual ``Input`` and an ``InputHistory`` instance.
        Submitting the input posts a ``ComposerSubmitted`` message.
        Empty submissions are silently ignored.

        Bindings:
        * Enter        — submit input, push to history
        * Up / Ctrl+P  — previous history item
        * Down / Ctrl+N — next history item
        * Escape       — clear input (plan cancellation handled by VnAlphaApp)
        * Ctrl+L       — clear_visible on the OutputStream (delegated to app)
        """

        class ComposerSubmitted(Message):
            """Posted when the user submits non-empty text from the composer."""

            def __init__(self, text: str) -> None:
                super().__init__()
                self.text = text

        DEFAULT_CSS = """
        ComposerInput {
            height: 3;
            min-height: 3;
            padding: 0;
            width: 100%;
        }
        ComposerInput > Input {
            height: 3;
            min-height: 3;
            border: round $accent;
            padding: 0 1;
            width: 100%;
        }
        #composer-suggestions {
            width: 100%;
            height: auto;
            max-height: 12;
            border: tall $accent;
            padding: 0 1;
            background: $surface;
            color: $text;
            display: none;
        }
        """

        BINDINGS = [
            Binding("ctrl+l", "clear_stream", "Clear output", show=False),
            Binding("up", "history_previous", "Previous history", show=False),
            Binding("down", "history_next", "Next history", show=False),
            Binding("ctrl+p", "history_previous", "Previous history", show=False),
            Binding("ctrl+n", "history_next", "Next history", show=False),
        ]

        _FALLBACK_COMMAND_NAMES: list[str] = [
            "analyze",
            "chat",
            "compare",
            "context",
            "copy",
            "data",
            "explain",
            "filter",
            "help",
            "history",
            "lineage",
            "market-regime",
            "model",
            "note",
            "quality",
            "research-plan",
            "sandbox",
            "scan",
            "sector-strength",
            "setup-evidence",
            "shortlist",
            "todo",
            "watchlist-summary",
        ]

        def __init__(self, history: InputHistory | None = None, **kwargs) -> None:
            super().__init__(**kwargs)
            self._history = history if history is not None else InputHistory()
            self._max_suggestions = 10
            self._command_names = self._load_command_names()
            self._logger = get_logger("vnalpha.tui.widgets.composer_input")

        def _debug_suggestion_event(self, event: str, **fields: object) -> None:
            if not _TUI_SUGGEST_DEBUG:
                return
            try:
                self._logger.debug(event, **fields)
            except Exception:  # noqa: BLE001
                pass

        @property
        def history(self) -> InputHistory:
            """Access the underlying InputHistory instance."""
            return self._history

        def compose(self) -> ComposeResult:
            yield Input(
                placeholder="Ask or run /command ...",
                id="composer-input-field",
            )
            yield Static("", id="composer-suggestions")

        def on_input_changed(self, event: Input.Changed) -> None:
            self._debug_suggestion_event("composer input changed", value=event.value)
            self._render_suggestions(event.value)

        def _load_command_names(self) -> list[str]:
            try:
                from vnalpha.tui.command_catalog import command_names

                return command_names()
            except Exception as exc:  # noqa: BLE001
                # A failed registry build (e.g. a missing optional dependency for
                # one handler) must not silently break slash-command discovery.
                self._debug_suggestion_event(
                    "command registry unavailable",
                    error=repr(exc),
                )
                try:
                    from vnalpha.observability.audit import log_audit

                    log_audit(
                        "TUI_COMMAND_NAMES_UNAVAILABLE",
                        "slash suggestions using fallback command list",
                        module="vnalpha.tui.widgets.composer_input",
                    )
                except Exception:  # noqa: BLE001
                    pass
                return self._FALLBACK_COMMAND_NAMES.copy()

        def _root_command_suggestions(self) -> list[str]:
            """Return the bounded discovery list with ``/help`` always reachable."""

            suggestions = self._command_names[: self._max_suggestions]
            if (
                "help" in self._command_names
                and "help" not in suggestions
                and suggestions
            ):
                suggestions[-1] = "help"
            return suggestions

        def _command_suggestions(self, raw_text: str) -> list[str]:
            if not raw_text.startswith("/"):
                return []

            if not self._command_names:
                return []

            body = raw_text[1:]
            if not body:
                return self._root_command_suggestions()

            base = body.split(None, 1)[0]
            if not base:
                return self._root_command_suggestions()

            return [
                name
                for name in self._command_names
                if name.lower().startswith(base.lower())
            ][: self._max_suggestions]

        def _render_suggestions(self, raw_text: str) -> None:
            suggestions = self._command_suggestions(raw_text)
            self._debug_suggestion_event(
                "render suggestions",
                raw_text=raw_text,
                suggestion_count=len(suggestions),
            )

            if not raw_text.startswith("/"):
                self._debug_suggestion_event("slash prefix missing")
                return self._hide_suggestions()

            try:
                panel = self.query_one("#composer-suggestions", Static)
            except Exception:
                return

            if not suggestions:
                self._debug_suggestion_event(
                    "hide suggestions",
                    raw_text=raw_text,
                    reason="no matches",
                )
                panel.display = False
                return

            panel.update("\n".join(f"/{name}" for name in suggestions))
            self._debug_suggestion_event(
                "show suggestions",
                raw_text=raw_text,
                suggestion_count=len(suggestions),
            )
            panel.display = True

        def _hide_suggestions(self) -> None:
            try:
                self._debug_suggestion_event(
                    "hide suggestions", reason="raw text reset"
                )
                self.query_one("#composer-suggestions", Static).display = False
            except Exception:
                pass

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Post ComposerSubmitted for non-empty text, push to history, and clear."""
            event.stop()
            raw = event.value.strip()
            if not raw:
                return
            event.input.clear()
            self._history.push(raw)
            self._history.reset_navigation()
            self._emit_history_pushed(raw)
            self._hide_suggestions()
            self.post_message(self.ComposerSubmitted(text=raw))

        # ------------------------------------------------------------------
        # History navigation actions
        # ------------------------------------------------------------------

        def action_history_previous(self) -> None:
            """Replace input with previous history item."""
            try:
                inp = self.query_one("#composer-input-field", Input)
                item = self._history.previous(inp.value)
                if item is not None:
                    inp.value = item
                    inp.cursor_position = len(item)
                    self._emit_history_nav("previous")
            except Exception:
                pass

        def action_history_next(self) -> None:
            """Replace input with next history item (or restore draft)."""
            try:
                inp = self.query_one("#composer-input-field", Input)
                item = self._history.next()
                if item is not None:
                    inp.value = item
                    inp.cursor_position = len(item)
                    if not self._history.navigating:
                        self._emit_history_draft_restored()
                    else:
                        self._emit_history_nav("next")
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Public API
        # ------------------------------------------------------------------

        def action_clear_stream(self) -> None:
            """Ask the app to clear the OutputStream via a message."""
            self.post_message(self.ComposerSubmitted(text="/clear"))

        def clear_input(self) -> None:
            """Programmatically clear the input field."""
            try:
                self.query_one("#composer-input-field", Input).clear()
                self._hide_suggestions()
            except Exception:
                pass

        def set_text(self, value: str) -> None:
            try:
                inp = self.query_one("#composer-input-field", Input)
                inp.value = value
                inp.cursor_position = len(value)
                self._render_suggestions(value)
            except Exception:
                pass

        def set_suggestion_limit(self, limit: int) -> None:
            self._max_suggestions = max(1, limit)
            try:
                value = self.query_one("#composer-input-field", Input).value
            except Exception:
                return
            self._render_suggestions(value)

        def focus_input(self) -> None:
            """Focus the underlying Input widget."""
            try:
                self.query_one("#composer-input-field", Input).focus()
            except Exception:
                pass

        def set_disabled(self, disabled: bool) -> None:
            """Enable/disable the input to indicate busy state."""
            try:
                inp = self.query_one("#composer-input-field", Input)
                inp.disabled = disabled
                if not disabled:
                    inp.focus()
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Observability
        # ------------------------------------------------------------------

        def _emit_history_pushed(self, text: str) -> None:
            try:
                from vnalpha.observability.audit import log_audit

                kind = "slash_command" if text.startswith("/") else "natural_language"
                log_audit(
                    "TUI_HISTORY_PUSHED",
                    f"kind={kind} len={len(text)}",
                    module="vnalpha.tui.widgets.composer_input",
                )
            except Exception:
                pass

        def _emit_history_nav(self, direction: str) -> None:
            try:
                from vnalpha.observability.audit import log_audit

                log_audit(
                    f"TUI_HISTORY_{direction.upper()}",
                    f"index={self._history._index} size={len(self._history)}",
                    module="vnalpha.tui.widgets.composer_input",
                )
            except Exception:
                pass

        def _emit_history_draft_restored(self) -> None:
            try:
                from vnalpha.observability.audit import log_audit

                log_audit(
                    "TUI_HISTORY_DRAFT_RESTORED",
                    f"size={len(self._history)}",
                    module="vnalpha.tui.widgets.composer_input",
                )
            except Exception:
                pass

else:

    class ComposerInput:  # type: ignore[no-redef]
        """Importable fallback used when textual is unavailable."""

        DEFAULT_CSS = ""
        BINDINGS = []

        class ComposerSubmitted:
            def __init__(self, text: str) -> None:
                self.text = text

        def __init__(self, history: InputHistory | None = None, **kwargs) -> None:
            self._history = history if history is not None else InputHistory()

        @property
        def history(self) -> InputHistory:
            return self._history

        def clear_input(self) -> None:
            pass

        def set_text(self, value: str) -> None:
            del value

        def focus_input(self) -> None:
            pass

        def set_disabled(self, disabled: bool) -> None:
            pass

        def set_suggestion_limit(self, limit: int) -> None:
            del limit
