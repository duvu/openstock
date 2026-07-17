from __future__ import annotations

import io
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_surface_reconciliation_preserves_foreign_handlers_and_restores_cli_console(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.core.logging import LogSurface, configure_logging

    stderr = io.StringIO()
    monkeypatch.setattr("sys.stderr", stderr)
    foreign_handler = logging.NullHandler()
    logging.getLogger().addHandler(foreign_handler)

    configure_logging(log_path=tmp_path / "vnalpha.log", surface=LogSurface.CLI)
    configure_logging(log_path=tmp_path / "vnalpha.log", surface=LogSurface.TUI)
    configure_logging(log_path=tmp_path / "vnalpha.log", surface=LogSurface.TUI)
    configure_logging(log_path=tmp_path / "vnalpha.log", surface=LogSurface.CLI)

    assert foreign_handler in logging.getLogger().handlers
    assert {handler.name for handler in _owned_handlers()} == {
        "vnalpha-queue",
        "vnalpha-console",
    }
    assert logging_module._QUEUE_LISTENER is not None


def test_configure_logging_defaults_to_cli_surface(tmp_path: Path) -> None:
    from vnalpha.core.logging import configure_logging

    configure_logging(log_path=tmp_path / "vnalpha.log")

    assert {handler.name for handler in _owned_handlers()} == {
        "vnalpha-queue",
        "vnalpha-console",
    }


def test_tui_surface_reports_file_initialization_failure_without_console(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.core.logging import LogSurface, configure_logging

    def raise_os_error(*args, **kwargs):
        del args, kwargs
        raise OSError("unavailable")

    monkeypatch.setattr(
        logging_module,
        "_SecureRotatingFileHandler",
        raise_os_error,
    )

    result = configure_logging(
        log_path=tmp_path / "vnalpha.log", surface=LogSurface.TUI
    )

    assert result.error_id == "TUI_LOGGING_INIT_FAILED"
    assert result.file_enabled is False
    assert result.console_enabled is False
    assert _owned_handlers() == []
    assert "unavailable" not in result.error_id


def test_repeated_tui_configuration_writes_each_event_once(tmp_path: Path) -> None:
    from vnalpha.core.logging import LogSurface, configure_logging, get_logger

    log_path = tmp_path / "vnalpha.log"
    for _ in range(2):
        configure_logging(log_path=log_path, surface=LogSurface.TUI)
        get_logger("surface-test").info("single tui record")
        assert logging_module._QUEUE_LISTENER is not None
        logging_module._QUEUE_LISTENER.stop()
    logging_module._QUEUE_LISTENER = None

    assert log_path.read_text(encoding="utf-8").count("single tui record") == 2


def test_configure_logging_tightens_existing_log_permissions(tmp_path: Path) -> None:
    from vnalpha.core.logging import LogSurface, configure_logging

    log_path = tmp_path / "vnalpha.log"
    log_path.write_text("existing\n", encoding="utf-8")
    log_path.chmod(0o644)

    configure_logging(log_path=log_path, surface=LogSurface.TUI)

    assert oct(log_path.stat().st_mode & 0o777) == "0o600"


def test_tui_command_emits_bounded_surface_transition_event() -> None:
    from vnalpha.cli_app.tui import tui
    from vnalpha.core.logging import LoggingConfigurationResult, LogSurface

    result = LoggingConfigurationResult(
        surface=LogSurface.TUI,
        file_enabled=True,
        console_enabled=False,
    )
    logger = MagicMock()
    with (
        patch("vnalpha.tui.app.VnAlphaApp") as app_class,
        patch("vnalpha.cli_app.tui.configure_logging", return_value=result),
        patch("vnalpha.cli_app.tui.get_logger", return_value=logger),
    ):
        tui(date=None)

    logger.info.assert_called_once_with(
        "LOGGING_SURFACE_CONFIGURED",
        surface="tui",
        file_enabled=True,
        console_enabled=False,
    )
    app_class.assert_called_once_with(date=None, logging_warning=None)
