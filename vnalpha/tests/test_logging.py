"""Tests for vnalpha.core.logging — configure_logging, get_logger, correlation ID."""

from __future__ import annotations

import logging
import logging.handlers
import time
from pathlib import Path

import pytest

import vnalpha.core.logging as _log_module

# ---------------------------------------------------------------------------
# Helpers to reset module state between tests
# ---------------------------------------------------------------------------


def _reset_logging_state() -> None:
    """Reset the module-level singleton so configure_logging() can run again."""
    # Stop any running listener
    if _log_module._QUEUE_LISTENER is not None:
        try:
            _log_module._QUEUE_LISTENER.stop()
        except Exception:
            pass
    _log_module._QUEUE_LISTENER = None
    _log_module._CONFIGURED = False

    # Remove all handlers from root logger
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    # Reset structlog so it is not cached
    import structlog

    structlog.reset_defaults()


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Ensure a clean logging state for each test."""
    _reset_logging_state()
    yield
    _reset_logging_state()


# ---------------------------------------------------------------------------
# Task 1.2 — configure_logging: creates file, sets up handlers
# ---------------------------------------------------------------------------


def test_configure_logging_creates_log_file(tmp_path: Path) -> None:
    """Given a tmp log_path, configure_logging must create the file."""
    from vnalpha.core.logging import configure_logging, get_logger

    log_path = tmp_path / "logs" / "test.log"
    configure_logging(level="DEBUG", log_path=log_path)

    logger = get_logger("test")
    logger.info("probe message")
    time.sleep(0.3)

    assert log_path.exists(), "log file was not created"


# ---------------------------------------------------------------------------
# Task 1.3 — get_logger: JSON output has required fields
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.4 — correlation ID: set_correlation_id / get_correlation_id
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.8 — correlation ID unification: core and observability share one value
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.9 — regression: no "unset" correlation IDs in instrumented commands
# ---------------------------------------------------------------------------
