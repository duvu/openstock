"""Data quality / provider health screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from vnalpha.core.text_safety import sanitize_text
from vnalpha.tui.error_boundary import capture_tui_exception, generic_load_error


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
                        sanitize_text(p.get("provider", "—")),
                        sanitize_text(p.get("status", "—")),
                        sanitize_text(p.get("dataset", "")),
                    )
                self.query_one("#quality-status", Static).update(
                    f"[green]{len(health.providers)} providers[/green]"
                )
            finally:
                client.close()
        except Exception as exc:
            capture_tui_exception(exc)
            self.query_one("#quality-status", Static).update(
                generic_load_error("Provider health")
            )

    def action_refresh(self) -> None:
        self._load_data()
