"""TUI Log Viewer screen — tails the vnalpha log file with level filtering."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, Static

from vnalpha.log_viewer import default_log_path, format_record_rich


class LogScreen(Screen):
    """Live log viewer with level filter buttons and file-tail worker."""

    TITLE = "Log Viewer"

    CSS = """
    LogScreen {
        layout: vertical;
        background: $background;
        overflow: hidden;
    }
    #log-body {
        height: 1fr;
        min-height: 0;
        overflow: hidden;
    }
    #log-toolbar {
        height: auto;
        max-height: 3;
        padding: 0 1;
        background: $surface;
        overflow: hidden;
    }
    #log-toolbar Button {
        margin: 0;
        min-width: 7;
    }
    #log-display {
        height: 1fr;
        min-height: 0;
        overflow-y: auto;
        border: solid $primary;
    }
    """

    LEVELS = ("ALL", "DEBUG", "INFO", "WARNING", "ERROR")
    MAX_RECORDS = 1_000
    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._active_level: str = "ALL"
        self._all_records: list[dict] = []
        self._file_pos: int = 0
        self._stopped: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="log-body"):
            yield Horizontal(
                Static("[b]Level:[/b]  ", id="level-label"),
                *[
                    Button(lvl, id=f"btn-{lvl}", variant="default")
                    for lvl in self.LEVELS
                ],
                id="log-toolbar",
            )
            yield RichLog(id="log-display", highlight=True, markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self._stopped = False
        self.run_worker(self._tail_log_async, exclusive=True)

    def on_unmount(self) -> None:
        self._stopped = True

    def action_close(self) -> None:
        self.app.pop_screen()

    async def _tail_log_async(self) -> None:
        """Async worker: poll the log file every 0.5 s for new lines."""
        log_path = default_log_path()
        while not self._stopped:
            if log_path.exists():
                await self._read_new_lines(log_path)
            await anyio.sleep(0.5)

    async def _read_new_lines(self, log_path: Path) -> None:
        """Read new lines from log file since last position and update display."""
        try:
            size = log_path.stat().st_size
            if size < self._file_pos:
                self._file_pos = 0
            if size == self._file_pos:
                return
            with log_path.open(encoding="utf-8", errors="replace") as fh:
                fh.seek(self._file_pos)
                new_records: list[dict] = []
                for raw_line in fh:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        rec = json.loads(raw_line)
                        new_records.append(rec)
                    except json.JSONDecodeError:
                        continue
                self._file_pos = fh.tell()
            for rec in new_records:
                self._all_records.append(rec)
                if len(self._all_records) > self.MAX_RECORDS:
                    self._all_records = self._all_records[-self.MAX_RECORDS :]
                if self._passes_filter(rec):
                    log_widget = self.query_one("#log-display", RichLog)
                    log_widget.write(format_record_rich(rec))
        except OSError:
            pass

    def _passes_filter(self, rec: dict) -> bool:
        """Return True if *rec* matches the active level filter."""
        if self._active_level == "ALL":
            return True
        level_order = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}
        min_ord = level_order.get(self._active_level.lower(), 0)
        rec_level = str(rec.get("level", "info")).lower()
        return level_order.get(rec_level, 0) >= min_ord

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle level filter button press."""
        btn_id = str(event.button.id or "")
        if not btn_id.startswith("btn-"):
            return
        new_level = btn_id[4:]
        if new_level not in self.LEVELS:
            return
        self._active_level = new_level
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Clear RichLog and re-render all records with the active filter."""
        try:
            log_widget = self.query_one("#log-display", RichLog)
            log_widget.clear()
            for rec in self._all_records:
                if self._passes_filter(rec):
                    log_widget.write(format_record_rich(rec))
        except Exception:
            pass
