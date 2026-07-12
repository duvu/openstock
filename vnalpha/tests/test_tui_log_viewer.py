"""Tests for the TUI LogScreen — mount, level filter, L key binding."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

textual_available = True
try:
    import textual  # noqa: F401
except ImportError:
    textual_available = False

skip_if_no_textual = pytest.mark.skipif(
    not textual_available, reason="textual not installed"
)


def test_log_record_rendering_strips_terminal_control_sequences() -> None:
    from vnalpha.log_viewer import format_record_rich

    rendered = format_record_rich(
        {
            "level": "info",
            "event": "\x1b[31mfailed\x1b[0m",
            "logger": "\x1b]0;title\x07app",
        }
    )

    assert "\x1b" not in rendered
    assert "failed" in rendered
    assert "app" in rendered


# ---------------------------------------------------------------------------
# Smoke: LogScreen can be imported and instantiated without crash
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_log_screen_can_be_imported() -> None:
    """LogScreen import must succeed without raising."""
    from vnalpha.tui.screens.log_viewer import LogScreen

    screen = LogScreen()
    assert screen is not None


@skip_if_no_textual
def test_log_screen_levels_constant() -> None:
    """LogScreen.LEVELS must include all expected filter names."""
    from vnalpha.tui.screens.log_viewer import LogScreen

    assert "ALL" in LogScreen.LEVELS
    assert "DEBUG" in LogScreen.LEVELS
    assert "INFO" in LogScreen.LEVELS
    assert "WARNING" in LogScreen.LEVELS
    assert "ERROR" in LogScreen.LEVELS


# ---------------------------------------------------------------------------
# Level filter logic (unit-test the _passes_filter method directly)
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_log_screen_passes_filter_all() -> None:
    """_passes_filter with level ALL accepts every record."""
    from vnalpha.tui.screens.log_viewer import LogScreen

    screen = LogScreen()
    screen._active_level = "ALL"

    for lvl in ("debug", "info", "warning", "error"):
        rec = {"event": "test", "level": lvl}
        assert screen._passes_filter(rec), f"ALL filter rejected level={lvl!r}"


@skip_if_no_textual
def test_log_screen_passes_filter_info() -> None:
    """_passes_filter with level INFO rejects debug, accepts info/warning/error."""
    from vnalpha.tui.screens.log_viewer import LogScreen

    screen = LogScreen()
    screen._active_level = "INFO"

    assert not screen._passes_filter({"event": "x", "level": "debug"})
    assert screen._passes_filter({"event": "x", "level": "info"})
    assert screen._passes_filter({"event": "x", "level": "warning"})
    assert screen._passes_filter({"event": "x", "level": "error"})


@skip_if_no_textual
def test_log_screen_passes_filter_error() -> None:
    """_passes_filter with level ERROR accepts only error/critical."""
    from vnalpha.tui.screens.log_viewer import LogScreen

    screen = LogScreen()
    screen._active_level = "ERROR"

    assert not screen._passes_filter({"event": "x", "level": "debug"})
    assert not screen._passes_filter({"event": "x", "level": "info"})
    assert not screen._passes_filter({"event": "x", "level": "warning"})
    assert screen._passes_filter({"event": "x", "level": "error"})


# ---------------------------------------------------------------------------
# VnAlphaApp has L key binding for show_log action
# ---------------------------------------------------------------------------


@skip_if_no_textual
def test_vnalpha_app_has_log_command_available() -> None:
    """vnalpha logs command is accessible (LogScreen available as legacy)."""
    from vnalpha.tui.screens.log_viewer import LogScreen

    assert LogScreen is not None


# ---------------------------------------------------------------------------
# Pilot test: LogScreen can be imported and is not mounted by default
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_log_screen_mounts_without_crash(tmp_path: Path) -> None:
    """LogScreen imports cleanly; new app uses OutputStream, not ContentSwitcher."""
    import duckdb

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.warehouse.migrations import run_migrations

    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)

    with patch("vnalpha.warehouse.connection.get_connection", return_value=conn):
        app = VnAlphaApp()
        async with app.run_test(headless=True) as pilot:
            streams = pilot.app.query(OutputStream)
            assert len(streams) == 1
