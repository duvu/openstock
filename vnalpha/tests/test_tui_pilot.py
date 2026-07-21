"""TUI pilot/integration tests — updated for opencode-like workspace.

Task coverage:
  4.1.1  App mounts
  4.1.2  OutputStream is the primary output region
  4.1.3  ComposerInput is the primary input region
  4.1.4  No ContentSwitcher in default DOM
  4.1.5  No ChatPanel in default DOM
  4.1.9  Legacy screens remain importable
  4.1.10 /clear clears visible stream only
  4.2.1  Empty warehouse: app mounts without crash
  4.2.2  Empty warehouse: show_detail does not crash
  4.2.6  No empty-state test crashes due to missing DuckDB file
  4.3.1  WatchlistScreen has select_symbol binding (legacy screen)
  4.3.3  Legacy TUI screens have meaningful TITLE attributes
  4.3.5  Manual TUI smoke steps documented
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


@skip_if_no_textual
@pytest.mark.asyncio
async def test_app_mounts(mock_get_connection):
    """VnAlphaApp mounts without errors (4.1.1)."""
    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp(date="2024-01-10")
    async with app.run_test(headless=True) as pilot:
        assert pilot.app is not None
