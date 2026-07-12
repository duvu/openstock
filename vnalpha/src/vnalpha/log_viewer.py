"""vnalpha log file reader — read, filter, and display structured log entries.

Used by the 'vnalpha log' CLI command and the TUI LogScreen.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from vnalpha.core.logging import _DEFAULT_LOG_PATH

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

LogRecord = dict[str, object]

# ---------------------------------------------------------------------------
# Log file location
# ---------------------------------------------------------------------------


def default_log_path() -> Path:
    """Return the log file path from env or default."""
    return Path(os.environ.get("VNALPHA_LOG_PATH", str(_DEFAULT_LOG_PATH)))


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_since(since: str) -> datetime | None:
    """Parse --since value into a UTC-aware datetime.

    Accepts:
    - "30m"  → 30 minutes ago
    - "1h"   → 1 hour ago
    - "2d"   → 2 days ago
    - ISO 8601 datetime string
    """
    if not since:
        return None

    now = datetime.now(tz=timezone.utc)

    if since.endswith("m"):
        return now - timedelta(minutes=int(since[:-1]))
    if since.endswith("h"):
        return now - timedelta(hours=int(since[:-1]))
    if since.endswith("d"):
        return now - timedelta(days=int(since[:-1]))

    # Try ISO format
    try:
        dt = datetime.fromisoformat(since)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _parse_record_timestamp(ts: str) -> datetime | None:
    """Parse a log record's ISO timestamp string into a UTC-aware datetime."""
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Core reader
# ---------------------------------------------------------------------------


def read_log_records(
    log_path: Path | None = None,
    *,
    level: str = "ALL",
    since: str | None = None,
    grep: str | None = None,
    tail: int | None = None,
) -> list[LogRecord]:
    """Read, parse, and filter JSON log records from *log_path*.

    Args:
        log_path: Path to the JSON-lines log file. Defaults to default_log_path().
        level:    Level filter — ALL, DEBUG, INFO, WARNING, ERROR (case-insensitive).
        since:    Time filter — "30m", "1h", "2d", or ISO datetime string.
        grep:     Substring filter on the 'event' field (case-insensitive).
        tail:     If set, return only the last N records after applying all other filters.
    """
    path = log_path or default_log_path()

    if not path.exists():
        return []

    since_dt = _parse_since(since) if since else None
    level_filter = level.upper() if level else "ALL"
    grep_lower = grep.lower() if grep else None

    level_order = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}
    min_level_ord = (
        level_order.get(level_filter.lower(), -1) if level_filter != "ALL" else -1
    )

    records: list[LogRecord] = []
    for rec in _iter_log_file(path):
        # Level filter
        if min_level_ord >= 0:
            rec_level = str(rec.get("level", "")).lower()
            if level_order.get(rec_level, 0) < min_level_ord:
                continue

        # Since filter
        if since_dt is not None:
            ts = rec.get("timestamp", "")
            rec_dt = _parse_record_timestamp(str(ts))
            if rec_dt is None or rec_dt < since_dt:
                continue

        # Grep filter
        if grep_lower is not None:
            event = str(rec.get("event", "")).lower()
            if grep_lower not in event:
                continue

        records.append(rec)

    if tail is not None and tail > 0:
        records = records[-tail:]

    return records


def _iter_log_file(path: Path) -> Iterator[LogRecord]:
    """Yield parsed JSON records from the log file, skipping invalid lines."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# ---------------------------------------------------------------------------
# Rich display helper
# ---------------------------------------------------------------------------

_LEVEL_COLORS = {
    "debug": "dim",
    "info": "green",
    "warning": "yellow",
    "error": "red",
    "critical": "bold red",
}
_TERMINAL_CONTROLS = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))|[\x00-\x08\x0b-\x1f\x7f]"
)


def _clean_log_text(value: object) -> str:
    return _TERMINAL_CONTROLS.sub("", str(value))


def format_record_rich(rec: LogRecord) -> str:
    """Format a log record as a Rich-markup string for console display."""
    level = _clean_log_text(rec.get("level", "info")).lower()
    color = _LEVEL_COLORS.get(level, "white")
    ts = _clean_log_text(rec.get("timestamp", ""))[:23]
    event = _clean_log_text(rec.get("event", ""))
    logger_name = _clean_log_text(rec.get("logger", ""))
    cid = _clean_log_text(rec.get("correlation_id", ""))

    extra_parts = []
    skip_keys = {"level", "timestamp", "event", "logger", "correlation_id"}
    for k, v in rec.items():
        if k not in skip_keys:
            extra_parts.append(f"{_clean_log_text(k)}={_clean_log_text(v)!r}")

    extra_str = "  " + "  ".join(extra_parts) if extra_parts else ""
    cid_str = f"  [dim]cid={cid[:8]}[/dim]" if cid else ""

    return (
        f"[dim]{ts}[/dim]  [{color}]{level.upper():<8}[/{color}]"
        f"  [cyan]{logger_name}[/cyan]  {event}{cid_str}{extra_str}"
    )
