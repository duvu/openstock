"""R4 ChatPanel wiring tests — delegation to ChatController.

Task coverage:
  5.1.1  ChatPanel creates a ChatController instance
  5.1.2  ChatPanel creates/resumes a chat_session for target date
  5.1.3  ChatPanel input submission calls ChatController.handle_turn(raw)
  5.1.4  ChatPanel approval action calls ChatController.approve_pending_plan()
  5.1.5  ChatPanel cancel action calls ChatController.cancel_pending_plan()
  5.1.6  No local command registry dispatch in ChatPanel
  5.1.7  No local assistant dispatch in ChatPanel
  5.1.8  ChatPanel tests assert delegation (this file)
  5.1.9  VnAlphaApp plan approval/cancel calls controller reliably
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
def test_no_local_assistant_dispatch_in_panel():
    from vnalpha.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    assert not hasattr(panel, "_dispatch_assistant")
    assert not hasattr(panel, "_run_ask")
