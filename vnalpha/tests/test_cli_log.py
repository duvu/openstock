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
