"""Rejected symbols screen."""
from __future__ import annotations

from datetime import date
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static


class RejectedScreen(Screen):
    """Shows symbols rejected during research pipeline stages."""

    TITLE = "Rejected Symbols"
    BINDINGS = [Binding("r", "refresh", "Refresh")]

    def __init__(self, target_date: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._target_date = target_date or str(date.today())

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(f"[bold]Rejected Symbols — {self._target_date}[/bold]"),
            DataTable(id="rejected-table"),
            Static("", id="rejected-status"),
            id="rejected-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#rejected-table", DataTable)
        table.add_columns("Symbol", "Stage", "Reason")
        self._load_data()

    def _load_data(self) -> None:
        try:
            from vnalpha.warehouse.connection import get_connection
            conn = get_connection()
            rows = conn.execute(
                "SELECT symbol, stage, reason FROM rejected_symbol WHERE date = ? ORDER BY symbol",
                [self._target_date],
            ).fetchall()
            table = self.query_one("#rejected-table", DataTable)
            table.clear()
            if not rows:
                self.query_one("#rejected-status", Static).update(
                    f"[green]No rejected symbols for {self._target_date}[/green]"
                )
                return
            for row in rows:
                table.add_row(row[0], row[1], row[2])
            self.query_one("#rejected-status", Static).update(
                f"[yellow]{len(rows)} symbols rejected[/yellow]"
            )
        except Exception as e:
            self.query_one("#rejected-status", Static).update(f"[red]Error: {e}[/red]")

    def action_refresh(self) -> None:
        self._load_data()
