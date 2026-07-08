"""Tests for the 'vnalpha log' CLI command — filter by level, since, grep, tail."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import vnalpha.core.logging as _log_module

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _reset() -> None:
    import logging

    import structlog

    if _log_module._QUEUE_LISTENER is not None:
        try:
            _log_module._QUEUE_LISTENER.stop()
        except Exception:
            pass
    _log_module._QUEUE_LISTENER = None
    _log_module._CONFIGURED = False

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    structlog.reset_defaults()


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    _reset()
    yield
    _reset()


def _write_log_file(log_path: Path, records: list[dict]) -> None:
    """Write JSON-line log records directly to a file (bypasses logging pipeline)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# Helpers to build test records
# ---------------------------------------------------------------------------


def _rec(event: str, level: str, ts: str = "2026-01-01T10:00:00Z", **kwargs) -> dict:
    return {
        "event": event,
        "level": level,
        "timestamp": ts,
        "logger": "test.module",
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_log_cmd_shows_all_records(tmp_path: Path) -> None:
    """Given a log file with 3 records, 'vnalpha log --tail 3' prints all 3."""
    from vnalpha.cli import app

    log_path = tmp_path / "vnalpha.log"
    _write_log_file(
        log_path,
        [
            _rec("event one", "info"),
            _rec("event two", "warning"),
            _rec("event three", "error"),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["log", "--tail", "3"],
        env={"VNALPHA_LOG_PATH": str(log_path)},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "event one" in result.output
    assert "event two" in result.output
    assert "event three" in result.output


def test_log_cmd_filter_by_level(tmp_path: Path) -> None:
    """--level ERROR shows only error records, not info/warning."""
    from vnalpha.cli import app

    log_path = tmp_path / "vnalpha.log"
    _write_log_file(
        log_path,
        [
            _rec("info event", "info"),
            _rec("warning event", "warning"),
            _rec("error event", "error"),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["log", "--level", "ERROR"],
        env={"VNALPHA_LOG_PATH": str(log_path)},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "error event" in result.output
    assert "info event" not in result.output
    assert "warning event" not in result.output


def test_log_cmd_filter_by_grep(tmp_path: Path) -> None:
    """--grep substring filters records by event field content."""
    from vnalpha.cli import app

    log_path = tmp_path / "vnalpha.log"
    _write_log_file(
        log_path,
        [
            _rec("sync started", "info"),
            _rec("warehouse ready", "info"),
            _rec("sync completed", "info"),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["log", "--grep", "sync"],
        env={"VNALPHA_LOG_PATH": str(log_path)},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "sync started" in result.output
    assert "sync completed" in result.output
    assert "warehouse ready" not in result.output


def test_log_cmd_tail_limits_output(tmp_path: Path) -> None:
    """--tail N returns at most N records (the last N)."""
    from vnalpha.cli import app

    log_path = tmp_path / "vnalpha.log"
    recs = [_rec(f"event {i}", "info") for i in range(10)]
    _write_log_file(log_path, recs)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["log", "--tail", "3"],
        env={"VNALPHA_LOG_PATH": str(log_path)},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    # Only the last 3 events should appear
    assert "event 7" in result.output
    assert "event 8" in result.output
    assert "event 9" in result.output
    assert "event 0" not in result.output


def test_log_cmd_filter_by_since(tmp_path: Path) -> None:
    """--since 1h shows only records from the last hour."""
    from datetime import datetime, timedelta, timezone

    from vnalpha.cli import app

    log_path = tmp_path / "vnalpha.log"
    now = datetime.now(tz=timezone.utc)
    old_ts = (now - timedelta(hours=2)).isoformat()
    recent_ts = (now - timedelta(minutes=5)).isoformat()

    _write_log_file(
        log_path,
        [
            _rec("old event", "info", ts=old_ts),
            _rec("recent event", "info", ts=recent_ts),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["log", "--since", "1h"],
        env={"VNALPHA_LOG_PATH": str(log_path)},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "recent event" in result.output
    assert "old event" not in result.output


def test_log_cmd_missing_log_file(tmp_path: Path) -> None:
    """When log file has no records, command exits 0 without crashing."""
    from vnalpha.cli import app

    nonexistent = tmp_path / "nonexistent.log"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["log"],
        env={"VNALPHA_LOG_PATH": str(nonexistent)},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
