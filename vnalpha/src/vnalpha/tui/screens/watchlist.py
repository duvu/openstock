"""Daily watchlist screen — ranked research candidates."""

from __future__ import annotations

from datetime import date
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static


class WatchlistScreen(Screen):
    """Shows ranked watchlist candidates for a given date."""

    TITLE = "Daily Watchlist"
    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "select_symbol", "Detail"),
    ]

    def __init__(self, target_date: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._target_date = target_date or str(date.today())

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(
                f"[bold]Research Candidates — {self._target_date}[/bold]", id="wl-title"
            ),
            Static("Loading...", id="wl-status"),
            DataTable(id="wl-table"),
            id="wl-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        table.add_columns("Rank", "Symbol", "Score", "Class", "Setup", "Risk Flags")
        self._load_data()

    def _load_data(self) -> None:
        try:
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.repositories import get_watchlist

            conn = get_connection()
            rows = get_watchlist(conn, self._target_date)
            table = self.query_one("#wl-table", DataTable)
            table.clear()
            if not rows:
                self.query_one("#wl-status", Static).update(
                    f"[yellow]No research candidates found for {self._target_date}.[/yellow] "
                    "Run: vnalpha score --date <date>"
                )
                return
            for row in rows:
                import json

                risk_flags = json.loads(row.get("risk_flags_json") or "[]")
                flags_str = ", ".join(risk_flags) if risk_flags else "—"
                table.add_row(
                    str(row["rank"]),
                    row["symbol"],
                    f"{row['score']:.3f}" if row["score"] else "—",
                    row.get("candidate_class") or "—",
                    row.get("setup_type") or "—",
                    flags_str,
                )
            self.query_one("#wl-status", Static).update(
                f"[green]{len(rows)} research candidates[/green]"
            )
        except Exception as e:
            self.query_one("#wl-status", Static).update(f"[red]Error: {e}[/red]")

    def action_refresh(self) -> None:
        self._load_data()

    def action_select_symbol(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        row_key = table.cursor_row
        if row_key is not None:
            try:
                cell = table.get_cell_at((row_key, 1))  # Symbol column
                self.app.show_detail(str(cell))
            except Exception:
                pass
