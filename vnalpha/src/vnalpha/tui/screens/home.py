"""Home screen — status overview."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static

from vnalpha.tui.error_boundary import (
    capture_tui_exception,
    generic_load_error,
    literal_text,
)


class HomeScreen(Screen):
    """Shows system status: warehouse path, last sync, last score run."""

    TITLE = "Home"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label("[bold]vnalpha Research Discovery[/bold]", id="title"),
            Static("", id="status"),
            id="home-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_status()

    def _load_status(self) -> None:
        try:
            from vnalpha.core.config import get_config

            cfg = get_config()
            status_lines = [
                f"Warehouse: {cfg.warehouse.path}",
                f"Service: {cfg.vnstock.base_url}",
                "",
                "Press w to view today's watchlist candidates.",
                "Press q to quit.",
            ]
            self.query_one("#status", Static).update(
                literal_text("\n".join(status_lines))
            )
        except Exception as exc:
            capture_tui_exception(exc)
            self.query_one("#status", Static).update(
                generic_load_error("System status")
            )
