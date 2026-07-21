from __future__ import annotations

import json
from pathlib import Path

from vnalpha.log_viewer import (
    format_record_plain,
    format_record_rich,
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
