"""vnalpha TUI application — research-only daily discovery interface."""
from __future__ import annotations

from typing import Optional
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer
from textual.screen import Screen

from vnalpha.tui.screens.watchlist import WatchlistScreen
from vnalpha.tui.screens.detail import DetailScreen
from vnalpha.tui.screens.rejected import RejectedScreen
from vnalpha.tui.screens.quality import QualityScreen
from vnalpha.tui.screens.home import HomeScreen


class VnAlphaApp(App):
    """vnalpha research discovery TUI.

    Keyboard navigation:
        h - Home
        w - Watchlist
        q - Quit
        ? - Help
    """

    CSS_PATH = None  # inline styles only for portability

    TITLE = "vnalpha | Research Discovery"
    SUB_TITLE = "Vietnamese Market Research Tool"

    BINDINGS = [
        Binding("h", "show_home", "Home"),
        Binding("w", "show_watchlist", "Watchlist"),
        Binding("r", "show_rejected", "Rejected"),
        Binding("p", "show_quality", "Quality"),
        Binding("q", "quit", "Quit"),
    ]

    SCREENS = {
        "home": HomeScreen,
        "watchlist": WatchlistScreen,
        "rejected": RejectedScreen,
        "quality": QualityScreen,
    }

    def __init__(self, date: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.target_date = date

    def on_mount(self) -> None:
        self.push_screen("watchlist")

    def action_show_home(self) -> None:
        self.push_screen("home")

    def action_show_watchlist(self) -> None:
        self.push_screen("watchlist")

    def action_show_rejected(self) -> None:
        self.push_screen("rejected")

    def action_show_quality(self) -> None:
        self.push_screen("quality")

    def show_detail(self, symbol: str) -> None:
        self.push_screen(DetailScreen(symbol=symbol))
