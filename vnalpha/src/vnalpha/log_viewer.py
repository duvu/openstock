"""vnalpha log file reader — read, filter, and display structured log entries.

Used by the ``vnalpha log`` CLI command and the inline TUI log drawer.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from rich.markup import escape

from vnalpha.core.logging import _DEFAULT_LOG_PATH
from vnalpha.core.text_safety import is_sensitive_key, redact_structure, sanitize_text

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

LogRecord = dict[str, object]
LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}

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

    records: list[LogRecord] = []
    for rec in _iter_log_file(path):
        if not record_passes_level(rec, level_filter):
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


def record_passes_level(record: LogRecord, minimum: str) -> bool:
    normalized = minimum.upper() if minimum else "ALL"
    if normalized == "ALL":
        return True
    threshold = LEVEL_ORDER.get(normalized.lower(), 0)
    record_level = str(record.get("level", "info")).lower()
    return LEVEL_ORDER.get(record_level, 0) >= threshold


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


def _clean_log_text(value: object) -> str:
    return sanitize_text(value, strip_rich=False)


def _plain_log_text(value: object) -> str:
    return sanitize_text(value)


def format_record_plain(rec: LogRecord) -> str:
    level = _plain_log_text(rec.get("level", "info")).upper()
    timestamp = _plain_log_text(rec.get("timestamp", ""))[:23]
    logger_name = _plain_log_text(rec.get("logger", ""))
    event = _plain_log_text(rec.get("event", ""))
    correlation_id = _plain_log_text(rec.get("correlation_id", ""))[:8]
    header = f"{timestamp}  {level:<8}  {logger_name}".strip()
    details = event
    if correlation_id:
        details += f"  cid={correlation_id}"
    skip_keys = {"level", "timestamp", "event", "logger", "correlation_id"}
    extras = [
        f"{_plain_log_text(key)}="
        f"{_plain_log_text('[REDACTED]' if is_sensitive_key(key) else redact_structure(value))!r}"
        for key, value in rec.items()
        if key not in skip_keys
    ]
    if extras:
        details += "  " + "  ".join(extras)
    return f"{header}\n{details}"


def format_record_rich(rec: LogRecord) -> str:
    """Format a log record as a Rich-markup string for console display."""
    level = _clean_log_text(rec.get("level", "info")).lower()
    color = _LEVEL_COLORS.get(level, "white")
    ts = _clean_log_text(rec.get("timestamp", ""))[:23]
    event = escape(_clean_log_text(rec.get("event", "")))
    logger_name = escape(_clean_log_text(rec.get("logger", "")))
    cid = escape(_clean_log_text(rec.get("correlation_id", "")))

    extra_parts = []
    skip_keys = {"level", "timestamp", "event", "logger", "correlation_id"}
    for k, v in rec.items():
        if k not in skip_keys:
            extra_parts.append(
                f"{escape(_clean_log_text(k))}="
                f"{escape(_clean_log_text('[REDACTED]' if is_sensitive_key(k) else redact_structure(v)))!r}"
            )

    extra_str = "  " + "  ".join(extra_parts) if extra_parts else ""
    cid_str = f"  [dim]cid={cid[:8]}[/dim]" if cid else ""

    return (
        f"[dim]{ts}[/dim]  [{color}]{level.upper():<8}[/{color}]"
        f"  [cyan]{logger_name}[/cyan]\n{event}{cid_str}{extra_str}"
    )


class IncrementalLogSource:
    def __init__(self, path: Path | None = None, *, max_records: int = 1_000) -> None:
        self.path = path or default_log_path()
        self.max_records = max(1, max_records)
        self._records: list[LogRecord] = []
        self._position = 0
        self._file_identity: tuple[int, int] | None = None
        self.last_error: str | None = None

    @property
    def records(self) -> tuple[LogRecord, ...]:
        return tuple(self._records)

    def filtered_records(self, level: str) -> tuple[LogRecord, ...]:
        return tuple(
            record for record in self._records if record_passes_level(record, level)
        )

    def filtered_plain_text(self, level: str) -> str:
        return "\n".join(
            format_record_plain(record) for record in self.filtered_records(level)
        )

    def read_new_records(self) -> list[LogRecord]:
        try:
            stat = self.path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if self._file_identity is None or identity != self._file_identity:
                self._position = self._bounded_tail_offset(stat.st_size)
            elif stat.st_size < self._position:
                self._position = 0
            self._file_identity = identity
            if stat.st_size == self._position:
                self.last_error = None
                return []
            new_records: list[LogRecord] = []
            with self.path.open(encoding="utf-8", errors="replace") as handle:
                handle.seek(self._position)
                for raw_line in handle:
                    try:
                        record = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict):
                        new_records.append(record)
                self._position = handle.tell()
        except FileNotFoundError:
            self.last_error = "Log file is unavailable."
            self._file_identity = None
            self._position = 0
            return []
        except OSError:
            self.last_error = "Log file is temporarily unreadable."
            return []

        self.last_error = None
        self._records.extend(new_records)
        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records :]
        return new_records

    def _bounded_tail_offset(self, file_size: int) -> int:
        if file_size == 0:
            return 0
        cursor = file_size
        buffered = b""
        with self.path.open("rb") as handle:
            while cursor > 0 and buffered.count(b"\n") <= self.max_records:
                block_size = min(65_536, cursor)
                cursor -= block_size
                handle.seek(cursor)
                buffered = handle.read(block_size) + buffered
        lines = buffered.splitlines(keepends=True)
        if len(lines) <= self.max_records:
            return cursor
        return file_size - sum(len(line) for line in lines[-self.max_records :])
