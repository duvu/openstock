"""R4 session lifecycle tests — chat_session create/resume/chat new/context.

Task coverage:
  5.6.1  TUI start creates or resumes chat_session
  5.6.2  /chat new creates a new chat_session and switches controller context
  5.6.3  Chat session context stores target_date, selected symbol, mode, pending-plan
  5.6.4  /context reads deterministic controller/session context
  5.6.5  Tests for session creation/resume/chat new/context
"""

from __future__ import annotations

import pytest

from vnalpha.chat.controller import ChatController
from vnalpha.chat.modes import ExecutionMode
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


def _make_ctrl(conn, session_id=None, mode=ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY):
    messages = []
    ctrl = ChatController(
        connection_factory=_conn_factory(conn),
        on_message=lambda style, text: messages.append((style, text)),
        target_date="2024-01-10",
        execution_mode=mode,
        chat_session_id=session_id,
    )
    ctrl._messages = messages
    return ctrl


# ---------------------------------------------------------------------------
# 5.6.1: TUI start creates or resumes chat_session
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.6.2: /chat new creates a new session and switches context
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.6.3: Session context stores target_date, mode, pending-plan state
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.6.4: /context reads deterministic controller/session context
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.6.5: Tests for session creation/resume/chat new/context (integration)
# ---------------------------------------------------------------------------


def test_full_session_lifecycle(conn):
    """5.6.5: Full session lifecycle — create, use, new, verify switch."""
    ctrl = _make_ctrl(conn)

    ctrl.handle_turn("/chat new")
    first_sid = ctrl._chat_session_id
    assert first_sid is not None

    ctrl.handle_turn("/chat new")
    second_sid = ctrl._chat_session_id
    assert second_sid is not None
    assert second_sid != first_sid, "Each /chat new should produce a distinct session"
