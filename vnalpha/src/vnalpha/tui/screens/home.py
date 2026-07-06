"""Home screen — status overview."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label
from textual.containers import Vertical


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
                f"[cyan]Warehouse:[/cyan] {cfg.warehouse.path}",
                f"[cyan]Service:[/cyan] {cfg.vnstock.base_url}",
                "",
                "Press [bold]w[/bold] to view today's watchlist candidates.",
                "Press [bold]q[/bold] to quit.",
            ]
            self.query_one("#status", Static).update("\n".join(status_lines))
        except Exception as e:
            self.query_one("#status", Static).update(f"[red]Error loading config: {e}[/red]")
