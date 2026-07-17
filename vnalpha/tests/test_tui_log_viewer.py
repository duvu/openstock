from __future__ import annotations

import json
from pathlib import Path

import pytest

from vnalpha.log_viewer import (
    IncrementalLogSource,
    format_record_plain,
    format_record_rich,
    record_passes_level,
)


def _append(path: Path, record: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def test_log_formatters_strip_controls_markup_and_secrets() -> None:
    credential = "live-" + "secret"
    record = {
        "timestamp": "2026-07-16T01:02:03+07:00",
        "level": "info",
        "event": f"\x1b[31m[bold]failed[/bold]\x1b[0m api_key={credential}",
        "logger": "\x1b]0;title\x07app",
        "correlation_id": "abc123456789",
    }

    plain = format_record_plain(record)
    rich = format_record_rich(record)

    assert "\x1b" not in plain
    assert "[bold]" not in plain
    assert credential not in plain
    assert "[REDACTED]" in plain
    assert "failed" in plain
    assert "app" in plain
    assert credential not in rich


def test_log_formatters_redact_nested_sensitive_mappings() -> None:
    record = {
        "level": "info",
        "event": "safe event",
        "context": {"credentials": {"api_key": "nested-secret"}},
    }

    plain = format_record_plain(record)
    rich = format_record_rich(record)

    assert "nested-secret" not in plain
    assert "nested-secret" not in rich
    assert "REDACTED" in plain


@pytest.mark.parametrize(
    ("minimum", "accepted"),
    [
        ("ALL", ["debug", "info", "warning", "error", "critical"]),
        ("DEBUG", ["debug", "info", "warning", "error", "critical"]),
        ("INFO", ["info", "warning", "error", "critical"]),
        ("WARNING", ["warning", "error", "critical"]),
        ("ERROR", ["error", "critical"]),
    ],
)
def test_shared_level_filter_semantics(minimum: str, accepted: list[str]) -> None:
    levels = ["debug", "info", "warning", "error", "critical"]

    actual = [
        level for level in levels if record_passes_level({"level": level}, minimum)
    ]

    assert actual == accepted


def test_incremental_source_handles_append_truncation_and_rotation(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "vnalpha.jsonl"
    _append(log_path, {"level": "info", "event": "first"})
    source = IncrementalLogSource(log_path, max_records=3)

    assert [record["event"] for record in source.read_new_records()] == ["first"]
    assert source.read_new_records() == []
    _append(log_path, {"level": "warning", "event": "second"})
    assert [record["event"] for record in source.read_new_records()] == ["second"]

    log_path.write_text(
        json.dumps({"level": "error", "event": "after truncate"}) + "\n",
        encoding="utf-8",
    )
    assert [record["event"] for record in source.read_new_records()] == [
        "after truncate"
    ]

    rotated = tmp_path / "vnalpha.jsonl.1"
    log_path.rename(rotated)
    _append(log_path, {"level": "debug", "event": "after rotate"})
    assert [record["event"] for record in source.read_new_records()] == ["after rotate"]
    assert len(source.records) == 3


def test_incremental_source_missing_file_is_bounded_empty(tmp_path: Path) -> None:
    source = IncrementalLogSource(tmp_path / "missing.jsonl")

    assert source.read_new_records() == []
    assert source.records == ()
    assert source.last_error == "Log file is unavailable."


@pytest.mark.asyncio
async def test_inline_drawer_retains_filter_and_starts_one_worker(
    tmp_path: Path,
) -> None:
    pytest.importorskip("textual")
    from textual.app import App, ComposeResult

    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

    log_path = tmp_path / "vnalpha.jsonl"
    _append(log_path, {"level": "debug", "event": "hidden detail"})
    _append(log_path, {"level": "error", "event": "visible error"})

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield DebugLogDrawer(log_path=log_path, id="debug-log-drawer")

    async with ProbeApp().run_test(headless=True) as pilot:
        drawer = pilot.app.query_one(DebugLogDrawer)
        await pilot.pause()
        drawer.set_level("ERROR")
        drawer.display = False
        drawer.display = True
        drawer.display = False
        drawer.display = True
        await pilot.pause()

        assert drawer.active_level == "ERROR"
        assert drawer.tail_worker_start_count == 1
        assert "visible error" in drawer.filtered_plain_text()
        assert "hidden detail" not in drawer.filtered_plain_text()


@pytest.mark.asyncio
async def test_inline_drawer_status_consumes_remaining_toolbar_width(
    tmp_path: Path,
) -> None:
    pytest.importorskip("textual")
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield DebugLogDrawer(log_path=tmp_path / "missing.jsonl")

    async with ProbeApp().run_test(headless=True, size=(100, 10)) as pilot:
        drawer = pilot.app.query_one(DebugLogDrawer)
        drawer.display = True
        drawer.styles.height = 8
        await pilot.pause()

        status = drawer.query_one("#debug-log-status", Static)

        assert status.region.width > len("Logs")
        assert status.styles.content_align_horizontal == "right"


@pytest.mark.asyncio
async def test_inline_drawer_rendered_records_match_bounded_copy_snapshot(
    tmp_path: Path,
) -> None:
    pytest.importorskip("textual")
    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

    log_path = tmp_path / "vnalpha.jsonl"
    _append(log_path, {"level": "info", "event": "initial-1"})
    _append(log_path, {"level": "info", "event": "initial-2"})

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield DebugLogDrawer(
                log_path=log_path,
                max_records=3,
                poll_interval=0.1,
            )

    async with ProbeApp().run_test(headless=True) as pilot:
        drawer = pilot.app.query_one(DebugLogDrawer)
        drawer.display = True
        drawer.styles.height = 10
        await pilot.pause(0.2)
        for index in range(1, 5):
            _append(log_path, {"level": "info", "event": f"append-{index}"})
        await pilot.pause(0.3)

        log = drawer.query_one("#debug-log-display", RichLog)
        rendered = "\n".join(
            getattr(line, "plain", getattr(line, "text", str(line)))
            for line in log.lines
        )
        copied = drawer.filtered_plain_text()

        assert "initial-1" not in rendered
        assert "initial-2" not in rendered
        assert "append-1" not in rendered
        assert all(f"append-{index}" in rendered for index in range(2, 5))
        assert all(f"append-{index}" in copied for index in range(2, 5))
        assert "append-1" not in copied


@pytest.mark.asyncio
async def test_compact_drawer_preserves_unbroken_event_identifier(
    tmp_path: Path,
) -> None:
    pytest.importorskip("textual")
    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

    log_path = tmp_path / "vnalpha.jsonl"
    _append(
        log_path,
        {
            "timestamp": "2026-07-16T01:02:03+07:00",
            "level": "info",
            "logger": "vnalpha.cli.tui",
            "event": "LOGGING_SURFACE_CONFIGURED",
        },
    )

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield DebugLogDrawer(log_path=log_path, poll_interval=0.1)

    async with ProbeApp().run_test(headless=True, size=(80, 10)) as pilot:
        drawer = pilot.app.query_one(DebugLogDrawer)
        drawer.display = True
        drawer.styles.height = 8
        await pilot.pause(0.2)
        log = drawer.query_one("#debug-log-display", RichLog)
        rendered = "\n".join(
            getattr(line, "plain", getattr(line, "text", str(line)))
            for line in log.lines
        )

        assert "LOGGING_SURFACE_CONFIGURED" in rendered
        assert "LOGGING_SURFACE_CONFIGURED" in drawer.filtered_plain_text()
