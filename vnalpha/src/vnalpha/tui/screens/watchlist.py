"""Daily watchlist screen — ranked research candidates."""

from __future__ import annotations

from datetime import date
from typing import Optional

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


class WatchlistScreen(Screen):
    """Shows ranked watchlist candidates for a given date."""

    TITLE = "Daily Watchlist"

    DEFAULT_CSS = """
    WatchlistScreen > Vertical {
        height: 1fr;
    }
    WatchlistScreen #wl-table {
        height: 1fr;
        min-height: 5;
    }
    """

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
                literal_text(
                    f"Research Candidates — {self._target_date}", style="bold"
                ),
                id="wl-title",
            ),
            Static("Loading...", id="wl-status"),
            DataTable(id="wl-table", cursor_type="row"),
            id="wl-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        table.add_columns(
            "Rank", "Symbol", "Score", "Class", "Setup", "Risk Flags", "Policy"
        )
        self._load_data()

    def _load_data(self) -> None:
        try:
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.repositories import get_watchlist

            conn = get_connection()
            try:
                rows = get_watchlist(conn, self._target_date)
            finally:
                conn.close()
            table = self.query_one("#wl-table", DataTable)
            table.clear()
            if not rows:
                self.query_one("#wl-status", Static).update(
                    literal_text(
                        f"No research candidates found for {self._target_date}. "
                        "Run: vnalpha score --date <date>",
                        style="yellow",
                    )
                )
                return
            for row in rows:
                import json

                risk_flags = json.loads(row.get("risk_flags_json") or "[]")
                flags_str = ", ".join(risk_flags) if risk_flags else "—"
                table.add_row(
                    str(row["rank"]),
                    sanitize_text(row["symbol"]),
                    f"{row['score']:.3f}" if row["score"] else "—",
                    sanitize_text(row.get("candidate_class") or "—"),
                    sanitize_text(row.get("setup_type") or "—"),
                    sanitize_text(flags_str),
                    sanitize_text(
                        f"{row.get('scoring_policy_version') or 'UNKNOWN'} / "
                        f"{row.get('scoring_policy_status') or 'UNKNOWN'}"
                    ),
                )
            status = (
                f"{len(rows)} research candidates | "
                f"policy={rows[0].get('scoring_policy_id') or 'UNKNOWN'}@"
                f"{rows[0].get('scoring_policy_version') or 'UNKNOWN'} | "
                f"hash={rows[0].get('scoring_policy_hash') or 'UNKNOWN'}"
            )
            self.query_one("#wl-status", Static).update(
                literal_text(status, style="green")
            )
        except Exception as exc:
            capture_tui_exception(exc)
            self.query_one("#wl-status", Static).update(generic_load_error("Watchlist"))

    def action_refresh(self) -> None:
        self._load_data()

    def action_select_symbol(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        row_key = table.cursor_row
        if row_key is not None:
            try:
                cell = table.get_cell_at((row_key, 1))  # Symbol column
                self.app.show_detail(str(cell))
            except Exception as exc:
                capture_tui_exception(exc)
