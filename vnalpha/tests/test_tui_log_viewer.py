"""Tests for the TUI LogScreen — mount, level filter, L key binding."""

from __future__ import annotations

from pathlib import Path

import pytest

textual_available = True
try:
    import textual  # noqa: F401
except ImportError:
    textual_available = False

skip_if_no_textual = pytest.mark.skipif(
    not textual_available, reason="textual not installed"
)


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
def test_vnalpha_app_has_l_binding() -> None:
    """VnAlphaApp.BINDINGS must include 'l' → 'show_log'."""
    from vnalpha.tui.app import VnAlphaApp

    binding_keys = {b.key: b.action for b in VnAlphaApp.BINDINGS}
    assert "l" in binding_keys, f"'l' binding not found. Keys: {list(binding_keys)}"
    assert binding_keys["l"] == "show_log", (
        f"'l' key bound to {binding_keys['l']!r}, expected 'show_log'"
    )


# ---------------------------------------------------------------------------
# Pilot test: LogScreen mounts without crash and L key activates it
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_log_screen_mounts_without_crash(tmp_path: Path) -> None:
    """LogScreen must mount inside the app without raising."""
    import os

    from textual.widgets import ContentSwitcher

    from vnalpha.tui.app import VnAlphaApp

    log_file = tmp_path / "test.log"
    log_file.write_text("")  # empty log file

    os.environ["VNALPHA_LOG_PATH"] = str(log_file)
    try:
        app = VnAlphaApp()
        async with app.run_test(headless=True) as pilot:
            await pilot.app.run_action("show_log")
            await pilot.pause(0.2)
            # Verify the log screen is now active
            switcher = app.query_one("#main-workspace", ContentSwitcher)
            assert switcher.current == "log", (
                f"ContentSwitcher current={switcher.current!r}, expected 'log'"
            )
    finally:
        os.environ.pop("VNALPHA_LOG_PATH", None)
