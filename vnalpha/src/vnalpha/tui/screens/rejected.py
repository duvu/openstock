"""Rejected symbols screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from vnalpha.core.text_safety import sanitize_text
from vnalpha.tui.error_boundary import (
    capture_tui_exception,
    generic_load_error,
    literal_text,
)
from vnalpha.tui.research_date import resolve_tui_research_date
from vnalpha.warehouse.connection import get_connection


class RejectedScreen(Screen):
    """Shows symbols rejected during research pipeline stages."""

    TITLE = "Rejected Symbols"
    BINDINGS = [Binding("r", "refresh", "Refresh")]

    def __init__(self, target_date: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._target_date = resolve_tui_research_date(target_date)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(
                literal_text(f"Rejected Symbols — {self._target_date}", style="bold")
            ),
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
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT symbol, stage, reason FROM rejected_symbol WHERE date = ? ORDER BY symbol",
                    [self._target_date],
                ).fetchall()
            finally:
                conn.close()
            table = self.query_one("#rejected-table", DataTable)
            table.clear()
            if not rows:
                self.query_one("#rejected-status", Static).update(
                    literal_text(
                        f"No rejected symbols for {self._target_date}", style="green"
                    )
                )
                return
            for row in rows:
                table.add_row(*(sanitize_text(value) for value in row))
            self.query_one("#rejected-status", Static).update(
                literal_text(f"{len(rows)} symbols rejected", style="yellow")
            )
        except Exception as exc:
            capture_tui_exception(exc)
            self.query_one("#rejected-status", Static).update(
                generic_load_error("Rejected-symbol data")
            )

    def action_refresh(self) -> None:
        self._load_data()
