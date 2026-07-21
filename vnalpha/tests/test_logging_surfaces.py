from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest
import structlog

import vnalpha.core.logging as logging_module


def _reset_logging_state() -> None:
    if logging_module._QUEUE_LISTENER is not None:
        logging_module._QUEUE_LISTENER.stop()
    logging_module._QUEUE_LISTENER = None
    logging_module._CONFIGURED = False

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    structlog.reset_defaults()


@pytest.fixture(autouse=True)
def reset_logging_state() -> None:
    _reset_logging_state()
    yield
    _reset_logging_state()


def _owned_handlers() -> list[logging.Handler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if (handler.name or "").startswith("vnalpha-")
    ]


def test_tui_surface_keeps_file_logging_and_silences_console(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.core.logging import LogSurface, configure_logging, get_logger

    stderr = io.StringIO()
    monkeypatch.setattr("sys.stderr", stderr)
    log_path = tmp_path / "vnalpha.log"

    configure_logging(log_path=log_path, surface=LogSurface.TUI)
    get_logger("surface-test").info("tui logging event")
    assert logging_module._QUEUE_LISTENER is not None
    logging_module._QUEUE_LISTENER.stop()
    logging_module._QUEUE_LISTENER = None

    assert stderr.getvalue() == ""
    assert "tui logging event" in log_path.read_text(encoding="utf-8")
    assert {handler.name for handler in _owned_handlers()} == {"vnalpha-queue"}
