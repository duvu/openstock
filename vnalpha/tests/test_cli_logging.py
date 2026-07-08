"""Task 2.3: Test that CLI commands emit structured log records to the log file."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

import vnalpha.core.logging as _log_module


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Reset logging state before and after each test."""
    _reset()
    yield
    _reset()


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


def test_vnalpha_init_emits_log_record(tmp_path: Path) -> None:
    """Given VNALPHA_LOG_PATH set, 'vnalpha init' must write at least one log record."""
    from vnalpha.cli import app

    log_path = tmp_path / "logs" / "vnalpha.log"
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["init"],
        env={
            "VNALPHA_LOG_PATH": str(log_path),
            "VNALPHA_LOG_LEVEL": "DEBUG",
        },
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"CLI exited non-zero: {result.output}"

    # Give the QueueListener thread time to flush
    time.sleep(0.5)

    assert log_path.exists(), "No log file created after vnalpha init"
    lines = [ln for ln in log_path.read_text().strip().split("\n") if ln]
    assert lines, "Log file is empty after vnalpha init"

    # Validate first record is valid JSON with required fields
    rec = json.loads(lines[0])
    assert "event" in rec, f"Missing 'event' field. Keys: {list(rec.keys())}"
    assert "level" in rec, f"Missing 'level' field. Keys: {list(rec.keys())}"
    assert "timestamp" in rec, f"Missing 'timestamp' field. Keys: {list(rec.keys())}"
