"""ComposerInput widget — single input bar for the chat-first TUI workspace."""

from __future__ import annotations

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.message import Message
    from textual.widget import Widget
    from textual.widgets import Input

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class ComposerInput(Widget):
        """
        Single-input composer bar for the chat-first TUI workspace.

        Owns exactly one Textual ``Input``. Submitting the input posts a
        ``ComposerSubmitted`` message. Empty submissions are silently ignored.
        The input is cleared after every submission.

        Bindings:
        * Enter        — submit input
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
            border: round $accent;
        }
        ComposerInput > Input {
            height: 1fr;
        }
        """

        BINDINGS = [
            Binding("ctrl+l", "clear_stream", "Clear output", show=False),
        ]

        def compose(self) -> ComposeResult:
            yield Input(
                placeholder="Ask or run /command ...",
                id="composer-input-field",
            )

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Post ComposerSubmitted for non-empty text and clear the input."""
            raw = event.value.strip()
            if not raw:
                return
            event.input.clear()
            self.post_message(self.ComposerSubmitted(text=raw))

        def action_clear_stream(self) -> None:
            """Ask the app to clear the OutputStream via a message."""
            self.post_message(self.ComposerSubmitted(text="/clear"))

        def clear_input(self) -> None:
            """Programmatically clear the input field."""
            try:
                self.query_one("#composer-input-field", Input).clear()
            except Exception:
                pass

        def focus_input(self) -> None:
            """Focus the underlying Input widget."""
            try:
                self.query_one("#composer-input-field", Input).focus()
            except Exception:
                pass

        def set_disabled(self, disabled: bool) -> None:
            """Enable/disable the input to indicate busy state."""
            try:
                self.query_one("#composer-input-field", Input).disabled = disabled
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

        def __init__(self, **kwargs) -> None:
            pass

        def clear_input(self) -> None:
            pass

        def focus_input(self) -> None:
            pass

        def set_disabled(self, disabled: bool) -> None:
            pass
