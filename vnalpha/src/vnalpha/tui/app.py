"""vnalpha TUI application — research-only daily discovery interface."""

from __future__ import annotations

from typing import Optional

from textual.app import App
from textual.binding import Binding

from vnalpha.core.dates import resolve_date
from vnalpha.tui.screens.command import CommandScreen
from vnalpha.tui.screens.detail import DetailScreen
from vnalpha.tui.screens.home import HomeScreen
from vnalpha.tui.screens.quality import QualityScreen
from vnalpha.tui.screens.rejected import RejectedScreen
from vnalpha.tui.screens.watchlist import WatchlistScreen


class VnAlphaApp(App):
    """vnalpha research discovery TUI.

    Keyboard navigation:
        h - Home
        w - Watchlist
        c - Command workspace (Phase 5.8)
        r - Rejected symbols
        p - Data quality
        q - Quit
    """

    CSS_PATH = None  # inline styles only for portability

    TITLE = "vnalpha | Research Discovery"
    SUB_TITLE = "Vietnamese Market Research Tool"

    BINDINGS = [
        Binding("h", "show_home", "Home"),
        Binding("w", "show_watchlist", "Watchlist"),
        Binding("c", "show_commands", "Commands"),
        Binding("r", "show_rejected", "Rejected"),
        Binding("p", "show_quality", "Quality"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, date: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.target_date: str = resolve_date(date)

    def on_mount(self) -> None:
        self.push_screen(WatchlistScreen(target_date=self.target_date))

    def action_show_home(self) -> None:
        self.push_screen(HomeScreen())

    def action_show_watchlist(self) -> None:
        self.push_screen(WatchlistScreen(target_date=self.target_date))

    def action_show_commands(self) -> None:
        self.push_screen(CommandScreen(target_date=self.target_date))

    def action_show_rejected(self) -> None:
        self.push_screen(RejectedScreen(target_date=self.target_date))

    def action_show_quality(self) -> None:
        self.push_screen(QualityScreen())

    def show_detail(self, symbol: str) -> None:
        self.push_screen(DetailScreen(symbol=symbol, target_date=self.target_date))
