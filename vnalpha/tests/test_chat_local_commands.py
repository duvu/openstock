"""Tests for Section 9: Chat-local commands (/clear /context /plan /trace /help)."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def in_memory_conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


def _make_conn_factory(conn: duckdb.DuckDBPyConnection):
    """Return a factory that wraps the shared connection without closing it."""

    class _NonClosingConn:
        def __init__(self, inner):
            self._inner = inner

        def close(self):
            pass  # don't close the fixture connection

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def factory():
        return _NonClosingConn(conn)

    return factory


def _make_ctrl(conn, *, session_id=None, target_date="2026-07-07"):
    from vnalpha.chat.controller import ChatController

    messages = []
    ctrl = ChatController(
        connection_factory=_make_conn_factory(conn),
        target_date=target_date,
        surface="tui-chat",
        on_message=lambda s, t: messages.append((s, t)),
        chat_session_id=session_id,
    )
    return ctrl, messages


# ---------------------------------------------------------------------------
# /chat new — create new session and reset context
# ---------------------------------------------------------------------------


def test_cmd_chat_new_via_handle_turn_creates_session(in_memory_conn):
    """/chat new creates a new chat_session through slash-command dispatch."""
    ctrl, messages = _make_ctrl(in_memory_conn)

    assert ctrl._chat_session_id is None

    ctrl.handle_turn("/chat new")

    assert ctrl._chat_session_id is not None
    assert any("new chat session" in text.lower() for _, text in messages)


# ---------------------------------------------------------------------------
# /clear — clear visible messages
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /context — show current ChatContext state
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /plan — show/toggle ExecutionMode
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /trace — show trace timeline
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /help — show all commands
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Integration: handle_turn routes to handle_chat_local_command
# ---------------------------------------------------------------------------
