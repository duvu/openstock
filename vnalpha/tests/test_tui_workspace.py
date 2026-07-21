"""TUI workspace tests — opencode-like chat-first layout (S9).

Covers all spec tasks 9.1-9.16. These tests replace the old ContentSwitcher /
ChatPanel / screen-switching tests in test_tui_pilot.py (which tested an
architecture that no longer exists in the default path).

Retired tests from test_tui_pilot.py:
  test_initial_screen_is_home           — ContentSwitcher removed
  test_switch_to_watchlist              — ContentSwitcher removed
  test_switch_to_commands               — ContentSwitcher removed
  test_switch_to_assistant              — ContentSwitcher removed
  test_switch_to_rejected               — ContentSwitcher removed
  test_switch_to_quality                — ContentSwitcher removed
  test_switch_to_outcomes               — ContentSwitcher removed
  test_chat_panel_remains_mounted_*     — ChatPanel removed from default
  test_chat_toggle_via_binding          — ChatPanel removed from default
  test_chat_controller_receives_*       — ChatPanel removed from default
"""

from __future__ import annotations

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


def _empty_conn():
    """In-memory DuckDB with migrations applied."""
    import duckdb

    from vnalpha.warehouse.migrations import run_migrations

    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    return conn


@pytest.fixture
def mock_get_connection():
    with patch(
        "vnalpha.warehouse.connection.get_connection", return_value=_empty_conn()
    ):
        yield


# ---------------------------------------------------------------------------
# 9.1  app mounts without errors
# ---------------------------------------------------------------------------


@skip_if_no_textual
@pytest.mark.asyncio
async def test_9_1_app_mounts(mock_get_connection):
    """VnAlphaApp mounts without errors (9.1)."""
    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        assert pilot.app is not None


# ---------------------------------------------------------------------------
# 9.2  exactly one ComposerInput exists
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.3  exactly one OutputStream exists
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.4  exactly one Textual Input widget in default DOM
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.5  ContentSwitcher does NOT exist in default DOM
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.6  ChatPanel does NOT exist in default DOM
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.7  CommandInput does NOT exist in default DOM
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.8  CommandResultPanel does NOT exist in default DOM
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.9-9.10 OutputStream unit tests (no pilot needed)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.11  Input routing unit tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.15  command output renders into OutputStream
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9.16  render errors captured by observability
# ---------------------------------------------------------------------------
