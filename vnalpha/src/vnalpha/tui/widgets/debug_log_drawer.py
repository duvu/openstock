from __future__ import annotations

from pathlib import Path

import anyio
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, RichLog, Static

from vnalpha.log_viewer import (
    IncrementalLogSource,
    format_record_rich,
)


class DebugLogDrawer(Widget):
    LEVELS = ("ALL", "DEBUG", "INFO", "WARNING", "ERROR")
    DEFAULT_CSS = """
    DebugLogDrawer {
        display: none;
        height: 0;
        min-height: 0;
        border: round $surface-darken-1;
        background: $surface;
        overflow: hidden;
    }
    DebugLogDrawer > #debug-log-toolbar {
        height: 1;
        min-height: 1;
        padding: 0 1;
        overflow: hidden;
    }
    DebugLogDrawer > #debug-log-toolbar Button {
        height: 1;
        min-height: 1;
        min-width: 5;
        margin: 0 1 0 0;
        padding: 0 1;
        border: none;
        content-align: center middle;
    }
    DebugLogDrawer > #debug-log-toolbar > #debug-log-status {
        width: 1fr;
        color: $text-muted;
        content-align: right middle;
    }
    DebugLogDrawer > #debug-log-display {
        height: 1fr;
        min-height: 0;
        padding: 0 1;
        overflow-x: hidden;
        overflow-y: auto;
        scrollbar-gutter: stable;
    }
    """

    def __init__(
        self,
        *,
        log_path: Path | None = None,
        max_records: int = 1_000,
        poll_interval: float = 0.5,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._source = IncrementalLogSource(log_path, max_records=max_records)
        self._active_level = "ALL"
        self._poll_interval = max(0.1, poll_interval)
        self._stopped = False
        self._tail_worker_started = False
        self._tail_worker_start_count = 0
        self._last_status_text = ""

    @property
    def active_level(self) -> str:
        return self._active_level

    @property
    def tail_worker_start_count(self) -> int:
        return self._tail_worker_start_count

    def compose(self) -> ComposeResult:
        with Horizontal(id="debug-log-toolbar"):
            for level in self.LEVELS:
                yield Button(level, id=f"debug-level-{level.lower()}")
            yield Static("Logs", id="debug-log-status")
        yield RichLog(
            id="debug-log-display",
            highlight=False,
            markup=True,
            wrap=True,
        )

    def on_mount(self) -> None:
        self._stopped = False
        self._refresh_level_buttons()
        if not self._tail_worker_started:
            self._tail_worker_started = True
            self._tail_worker_start_count += 1
            self.run_worker(
                self._tail_log,
                name="debug-log-tail",
                group="debug-log-tail",
                exclusive=True,
            )

    def on_unmount(self) -> None:
        self._stopped = True

    def set_level(self, level: str) -> None:
        normalized = level.upper()
        if normalized not in self.LEVELS:
            raise ValueError(f"Unsupported log level: {level}")
        self._active_level = normalized
        self._refresh_level_buttons()
        self._refresh_display()

    def filtered_plain_text(self) -> str:
        return self._source.filtered_plain_text(self._active_level)

    def page_up(self) -> None:
        self._scroll("scroll_page_up")

    def page_down(self) -> None:
        self._scroll("scroll_page_down")

    def home(self) -> None:
        self._scroll("scroll_home")

    def end(self) -> None:
        self._scroll("scroll_end")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = str(event.button.id or "")
        prefix = "debug-level-"
        if button_id.startswith(prefix):
            self.set_level(button_id.removeprefix(prefix))

    async def _tail_log(self) -> None:
        while not self._stopped:
            new_records = await anyio.to_thread.run_sync(self._source.read_new_records)
            if new_records:
                self._refresh_display()
            self._refresh_status()
            await anyio.sleep(self._poll_interval)

    def _refresh_display(self) -> None:
        try:
            log = self.query_one("#debug-log-display", RichLog)
            log.clear()
            for record in self._source.filtered_records(self._active_level):
                log.write(format_record_rich(record))
            self._refresh_status()
        except Exception:
            pass

    def _refresh_level_buttons(self) -> None:
        for level in self.LEVELS:
            try:
                button = self.query_one(f"#debug-level-{level.lower()}", Button)
                button.variant = "primary" if level == self._active_level else "default"
            except Exception:
                pass

    def _refresh_status(self) -> None:
        try:
            status = self.query_one("#debug-log-status", Static)
            if self._source.last_error:
                status_text = self._source.last_error
            else:
                count = len(self._source.filtered_records(self._active_level))
                status_text = f"{self._active_level} · {count} records"
            if status_text != self._last_status_text:
                self._last_status_text = status_text
                status.update(status_text)
        except Exception:
            pass

    def _scroll(self, method: str) -> None:
        try:
            log = self.query_one("#debug-log-display", RichLog)
            scroll = getattr(log, method, None)
            if callable(scroll):
                scroll(animate=False)
        except Exception:
            pass
