"""Data quality / provider health screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static, Label
from textual.containers import Vertical
from textual.binding import Binding


class QualityScreen(Screen):
    """Shows data quality and provider status information."""

    TITLE = "Data Quality"
    BINDINGS = [Binding("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label("[bold]Provider / Data Quality Status[/bold]"),
            DataTable(id="quality-table"),
            Static("", id="quality-status"),
            id="quality-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#quality-table", DataTable)
        table.add_columns("Provider", "Status", "Details")
        self._load_data()

    def _load_data(self) -> None:
        try:
            from vnalpha.clients.vnstock.client import VnstockClient
            from vnalpha.core.config import get_config
            cfg = get_config()
            client = VnstockClient(base_url=cfg.vnstock.base_url, timeout=5.0)
            try:
                health = client.get_provider_health()
                table = self.query_one("#quality-table", DataTable)
                table.clear()
                for p in health.providers:
                    table.add_row(
                        p.get("provider", "—"),
                        p.get("status", "—"),
                        p.get("dataset", ""),
                    )
                self.query_one("#quality-status", Static).update(
                    f"[green]{len(health.providers)} providers[/green]"
                )
            finally:
                client.close()
        except Exception as e:
            self.query_one("#quality-status", Static).update(
                f"[yellow]Service unavailable: {e}[/yellow]"
            )

    def action_refresh(self) -> None:
        self._load_data()
