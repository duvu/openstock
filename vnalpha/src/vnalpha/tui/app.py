"""vnalpha TUI application — research-only daily discovery interface."""

from __future__ import annotations

from typing import Optional

from vnalpha.core.dates import resolve_date

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.message import Message

    from vnalpha.tui.screens.assistant import AssistantScreen
    from vnalpha.tui.screens.command import CommandScreen
    from vnalpha.tui.screens.detail import DetailScreen
    from vnalpha.tui.screens.home import HomeScreen
    from vnalpha.tui.screens.outcomes import OutcomeScreen
    from vnalpha.tui.screens.quality import QualityScreen
    from vnalpha.tui.screens.rejected import RejectedScreen
    from vnalpha.tui.screens.watchlist import WatchlistScreen
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class PlanCancelRequested(Message):
        """Posted when the user requests a pending plan to be cancelled."""

    class VnAlphaApp(App):
        """vnalpha research discovery TUI — split-pane with persistent chat panel."""

        CSS_PATH = None  # inline styles only for portability

        CSS = """
        VnAlphaApp > Vertical {
            height: 1fr;
        }
        """

        TITLE = "vnalpha | Research Discovery"
        SUB_TITLE = "Vietnamese Market Research Tool"

        BINDINGS = [
            Binding("h", "show_home", "Home"),
            Binding("w", "show_watchlist", "Watchlist"),
            Binding("c", "show_commands", "Commands"),
            Binding("a", "show_assistant", "Ask"),
            Binding("r", "show_rejected", "Rejected"),
            Binding("p", "show_quality", "Quality"),
            Binding("o", "show_outcomes", "Outcomes"),
            Binding("q", "quit", "Quit"),
            Binding("ctrl+backslash", "toggle_chat", "Toggle chat"),
            Binding("ctrl+slash", "focus_chat", "Focus chat"),
            Binding("escape", "cancel_pending_plan", "Cancel plan", show=False),
        ]

        def __init__(self, date: Optional[str] = None, **kwargs):
            super().__init__(**kwargs)
            self.target_date: str = resolve_date(date)

        def compose(self) -> ComposeResult:
            """Yield screen area (70%) then persistent ChatPanel (30%)."""
            with Vertical():
                yield ChatPanel(target_date=self.target_date, id="chat-panel")

        def on_mount(self) -> None:
            self.push_screen(WatchlistScreen(target_date=self.target_date))

        def action_show_home(self) -> None:
            self.push_screen(HomeScreen())

        def action_show_watchlist(self) -> None:
            self.push_screen(WatchlistScreen(target_date=self.target_date))

        def action_show_commands(self) -> None:
            self.push_screen(CommandScreen(target_date=self.target_date))

        def action_show_assistant(self) -> None:
            self.push_screen(AssistantScreen(target_date=self.target_date))

        def action_show_rejected(self) -> None:
            self.push_screen(RejectedScreen(target_date=self.target_date))

        def action_show_quality(self) -> None:
            self.push_screen(QualityScreen())

        def action_show_outcomes(self) -> None:
            self.push_screen(OutcomeScreen(target_date=self.target_date))

        def show_detail(self, symbol: str) -> None:
            self.push_screen(DetailScreen(symbol=symbol, target_date=self.target_date))

        def action_toggle_chat(self) -> None:
            """Toggle ChatPanel visibility."""
            panel = self.query_one("#chat-panel", ChatPanel)
            panel.display = not panel.display

        def action_focus_chat(self) -> None:
            """Focus the chat input widget."""
            panel = self.query_one("#chat-panel", ChatPanel)
            panel.action_focus_input()

        def action_cancel_pending_plan(self) -> None:
            """Post PlanCancelRequested message so subscribers can cancel plans."""
            self.post_message(PlanCancelRequested())

        def action_approve_plan(self) -> None:
            """Approve the pending plan in the ChatPanel's controller (if any)."""
            try:
                panel = self.query_one("#chat-panel", ChatPanel)
                controller = getattr(panel, "_chat_controller", None)
                if controller is not None and controller._pending_plan is not None:
                    controller.approve_pending_plan()
            except Exception:
                pass

else:

    class _FallbackBinding:
        def __init__(self, key: str, action: str, description: str) -> None:
            self.key = key
            self.action = action
            self.description = description

    class VnAlphaApp:  # type: ignore[no-redef]
        """Importable fallback used when textual is unavailable."""

        TITLE = "vnalpha | Research Discovery"
        SUB_TITLE = "Vietnamese Market Research Tool"
        BINDINGS = [
            _FallbackBinding("h", "show_home", "Home"),
            _FallbackBinding("w", "show_watchlist", "Watchlist"),
            _FallbackBinding("c", "show_commands", "Commands"),
            _FallbackBinding("a", "show_assistant", "Ask"),
            _FallbackBinding("r", "show_rejected", "Rejected"),
            _FallbackBinding("p", "show_quality", "Quality"),
            _FallbackBinding("o", "show_outcomes", "Outcomes"),
            _FallbackBinding("q", "quit", "Quit"),
            _FallbackBinding("ctrl+backslash", "toggle_chat", "Toggle chat"),
            _FallbackBinding("ctrl+slash", "focus_chat", "Focus chat"),
        ]

        def __init__(self, date: Optional[str] = None, **kwargs):
            self.target_date: str = resolve_date(date)

        def run(self) -> None:
            raise ImportError("textual is required for the TUI")
