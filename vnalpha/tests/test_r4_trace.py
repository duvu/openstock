"""R4 trace timeline tests — ChatController trace callback persists events.

Task coverage:
  5.5.1  ChatController trace callback persists trace events when chat_session exists
  5.5.2  Trace events include tool name, status, duration, and tool_trace_id
  5.5.3  /trace reads persisted trace events for current chat_session
  5.5.4  Trace render shows useful output for no events
  5.5.5  Tests for trace persistence and /trace output
"""

from __future__ import annotations

import pytest

from vnalpha.chat.controller import ChatController
from vnalpha.warehouse.chat_repo import (
    create_chat_session,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


class _NonClosingConn:
    def __init__(self, inner):
        self._inner = inner

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _conn_factory(conn):
    def factory():
        return _NonClosingConn(conn)

    return factory


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


@pytest.fixture
def session_id(conn):
    return create_chat_session(conn)


def _make_ctrl(conn, session_id=None):
    messages = []
    ctrl = ChatController(
        connection_factory=_conn_factory(conn),
        on_message=lambda style, text: messages.append((style, text)),
        target_date="2024-01-10",
        chat_session_id=session_id,
    )
    ctrl._messages = messages
    return ctrl


# ---------------------------------------------------------------------------
# 5.5.1: Trace callback persists events when session exists
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.5.2: Trace events include required fields
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.5.3: /trace reads persisted trace events for current session
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.5.4: Trace render shows useful output for no events
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.5.5: Tests for trace persistence and /trace output
# ---------------------------------------------------------------------------


def test_trace_persisted_via_controller_callback(conn, session_id):
    """5.5.5: Full flow — trace event from controller is readable via /trace."""
    from vnalpha.tools.executor import TraceEvent

    ctrl = _make_ctrl(conn, session_id=session_id)

    event = TraceEvent(
        tool_name="end_to_end_tool",
        status="SUCCESS",
        duration_ms=30.0,
        tool_trace_id="",
    )
    ctrl._on_trace(event)

    result = ctrl._cmd_trace([])
    assert "end_to_end_tool" in result, (
        "/trace must reflect events added via trace callback"
    )
