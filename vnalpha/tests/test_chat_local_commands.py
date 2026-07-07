"""Tests for Section 9: Chat-local commands (/new /clear /context /plan /trace /help)."""

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
# /new — create new session and reset context
# ---------------------------------------------------------------------------


def test_cmd_new_creates_session(in_memory_conn):
    """/new creates a new chat_session row and returns confirmation."""
    ctrl, messages = _make_ctrl(in_memory_conn)

    assert ctrl._chat_session_id is None

    result = ctrl.handle_chat_local_command("new", [])

    assert ctrl._chat_session_id is not None
    assert "new chat session" in result.lower() or "session" in result.lower()


def test_cmd_new_resets_pending_plan(in_memory_conn):
    """/new clears any pending plan state."""
    from unittest.mock import MagicMock

    ctrl, _ = _make_ctrl(in_memory_conn)
    ctrl._pending_plan = MagicMock()
    ctrl._pending_plan_turn_context = {"question": "something"}

    ctrl.handle_chat_local_command("new", [])

    assert ctrl._pending_plan is None
    assert ctrl._pending_plan_turn_context is None


def test_cmd_new_session_id_changes(in_memory_conn):
    """/new gives a different session_id on each call."""
    ctrl, _ = _make_ctrl(in_memory_conn)

    ctrl.handle_chat_local_command("new", [])
    first_id = ctrl._chat_session_id

    ctrl.handle_chat_local_command("new", [])
    second_id = ctrl._chat_session_id

    assert first_id != second_id


# ---------------------------------------------------------------------------
# /clear — clear visible messages
# ---------------------------------------------------------------------------


def test_cmd_clear_calls_clear_visible_messages(in_memory_conn):
    """/clear calls clear_visible_messages for the current session."""
    from vnalpha.warehouse.chat_repo import append_chat_message, create_chat_session

    session_id = create_chat_session(in_memory_conn, surface="tui-chat")
    append_chat_message(
        in_memory_conn,
        chat_session_id=session_id,
        role="user",
        content="hello",
    )

    ctrl, _ = _make_ctrl(in_memory_conn, session_id=session_id)
    result = ctrl.handle_chat_local_command("clear", [])

    # Soft-hide: row still exists but is_visible=false
    row = in_memory_conn.execute(
        "SELECT is_visible FROM chat_message WHERE chat_session_id = ?",
        [session_id],
    ).fetchone()
    assert row is not None
    assert row[0] is False

    assert "cleared" in result.lower()


def test_cmd_clear_forget_also_deletes(in_memory_conn):
    """/clear --forget also deletes transcript rows (same behaviour since clear_visible_messages deletes)."""
    from vnalpha.warehouse.chat_repo import append_chat_message, create_chat_session

    session_id = create_chat_session(in_memory_conn, surface="tui-chat")
    append_chat_message(
        in_memory_conn,
        chat_session_id=session_id,
        role="user",
        content="some message",
    )

    ctrl, _ = _make_ctrl(in_memory_conn, session_id=session_id)
    result = ctrl.handle_chat_local_command("clear", ["--forget"])

    row = in_memory_conn.execute(
        "SELECT COUNT(*) FROM chat_message WHERE chat_session_id = ?",
        [session_id],
    ).fetchone()
    assert row[0] == 0

    # With --forget the response should mention deletion or forget
    assert "deleted" in result.lower() or "cleared" in result.lower()


def test_cmd_clear_no_session_returns_warning(in_memory_conn):
    """/clear with no active session returns a descriptive warning."""
    ctrl, _ = _make_ctrl(in_memory_conn, session_id=None)
    result = ctrl.handle_chat_local_command("clear", [])
    assert "no active" in result.lower() or "no session" in result.lower()


# ---------------------------------------------------------------------------
# /context — show current ChatContext state
# ---------------------------------------------------------------------------


def test_cmd_context_returns_context_string(in_memory_conn):
    """/context returns a non-empty string containing context field info."""
    ctrl, _ = _make_ctrl(in_memory_conn, session_id="test-session-id")

    result = ctrl.handle_chat_local_command("context", [])

    assert isinstance(result, str)
    assert len(result) > 0
    assert (
        "context" in result.lower()
        or "session" in result.lower()
        or "mode" in result.lower()
    )


def test_cmd_context_includes_execution_mode(in_memory_conn):
    """/context shows execution_mode value."""
    ctrl, _ = _make_ctrl(in_memory_conn)

    result = ctrl.handle_chat_local_command("context", [])

    # execution_mode should always appear
    assert "auto" in result or "plan" in result or "execution_mode" in result.lower()


def test_cmd_context_no_session_no_crash(in_memory_conn):
    """/context works even when no session is active (returns context info not error)."""
    ctrl, _ = _make_ctrl(in_memory_conn, session_id=None)
    result = ctrl.handle_chat_local_command("context", [])
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# /plan — show/toggle ExecutionMode
# ---------------------------------------------------------------------------


def test_cmd_plan_shows_current_mode(in_memory_conn):
    """/plan with no args returns the current execution mode."""
    from vnalpha.chat.modes import ExecutionMode

    ctrl, _ = _make_ctrl(in_memory_conn)
    assert ctrl.execution_mode == ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY

    result = ctrl.handle_chat_local_command("plan", [])
    assert "auto" in result.lower() or "plan" in result.lower()


def test_cmd_plan_on_sets_plan_then_approve(in_memory_conn):
    """/plan on sets execution_mode to PLAN_THEN_APPROVE."""
    from vnalpha.chat.modes import ExecutionMode

    ctrl, _ = _make_ctrl(in_memory_conn)
    ctrl.handle_chat_local_command("plan", ["on"])
    assert ctrl.execution_mode == ExecutionMode.PLAN_THEN_APPROVE


def test_cmd_plan_off_sets_auto_execute(in_memory_conn):
    """/plan off sets execution_mode to AUTO_EXECUTE_SAFE_READ_ONLY."""
    from vnalpha.chat.modes import ExecutionMode

    ctrl, _ = _make_ctrl(in_memory_conn)
    ctrl.execution_mode = ExecutionMode.PLAN_THEN_APPROVE  # start with something else
    ctrl.handle_chat_local_command("plan", ["off"])
    assert ctrl.execution_mode == ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY


def test_cmd_plan_only_sets_plan_only(in_memory_conn):
    """/plan only sets execution_mode to PLAN_ONLY."""
    from vnalpha.chat.modes import ExecutionMode

    ctrl, _ = _make_ctrl(in_memory_conn)
    ctrl.handle_chat_local_command("plan", ["only"])
    assert ctrl.execution_mode == ExecutionMode.PLAN_ONLY


# ---------------------------------------------------------------------------
# /trace — show trace timeline
# ---------------------------------------------------------------------------


def test_cmd_trace_returns_trace_events(in_memory_conn):
    """/trace returns formatted trace event string when events exist."""
    from vnalpha.warehouse.chat_repo import append_trace_event, create_chat_session

    session_id = create_chat_session(in_memory_conn, surface="tui-chat")
    append_trace_event(
        in_memory_conn,
        chat_session_id=session_id,
        tool_name="watchlist.scan",
        status="SUCCESS",
        elapsed_ms=42.0,
    )

    ctrl, _ = _make_ctrl(in_memory_conn, session_id=session_id)
    result = ctrl.handle_chat_local_command("trace", [])

    assert "watchlist.scan" in result or "trace" in result.lower()
    assert isinstance(result, str)


def test_cmd_trace_no_session_returns_message(in_memory_conn):
    """/trace with no session returns descriptive message (not crash)."""
    ctrl, _ = _make_ctrl(in_memory_conn, session_id=None)
    result = ctrl.handle_chat_local_command("trace", [])
    assert isinstance(result, str)
    assert (
        "no active" in result.lower()
        or "no trace" in result.lower()
        or "no session" in result.lower()
    )


def test_cmd_trace_empty_session_returns_no_events(in_memory_conn):
    """/trace with a session that has no trace events returns appropriate message."""
    from vnalpha.warehouse.chat_repo import create_chat_session

    session_id = create_chat_session(in_memory_conn, surface="tui-chat")
    ctrl, _ = _make_ctrl(in_memory_conn, session_id=session_id)

    result = ctrl.handle_chat_local_command("trace", [])
    assert "no trace" in result.lower() or "0 event" in result.lower()


# ---------------------------------------------------------------------------
# /help — show all commands
# ---------------------------------------------------------------------------


def test_cmd_help_contains_all_local_commands(in_memory_conn):
    """/help output mentions all 6 chat-local commands."""
    ctrl, _ = _make_ctrl(in_memory_conn)
    result = ctrl.handle_chat_local_command("help", [])

    for cmd in ("/new", "/clear", "/context", "/plan", "/trace", "/help"):
        assert cmd in result, f"Expected '{cmd}' in /help output"


def test_cmd_help_mentions_research_commands(in_memory_conn):
    """/help output mentions key research slash commands."""
    ctrl, _ = _make_ctrl(in_memory_conn)
    result = ctrl.handle_chat_local_command("help", [])

    for cmd in ("/scan", "/filter", "/quality", "/explain"):
        assert cmd in result, f"Expected research command '{cmd}' in /help output"


def test_cmd_help_returns_non_empty_string(in_memory_conn):
    """/help returns a non-empty string."""
    ctrl, _ = _make_ctrl(in_memory_conn)
    result = ctrl.handle_chat_local_command("help", [])
    assert isinstance(result, str)
    assert len(result) > 50


# ---------------------------------------------------------------------------
# Integration: handle_turn routes to handle_chat_local_command
# ---------------------------------------------------------------------------


def test_handle_turn_routes_help_to_chat_local(in_memory_conn):
    """/help via handle_turn emits a message with command listing."""
    ctrl, messages = _make_ctrl(in_memory_conn)

    ctrl.handle_turn("/help")

    all_text = " ".join(t for _, t in messages)
    assert "/new" in all_text
    assert "/clear" in all_text


def test_handle_turn_routes_plan_on(in_memory_conn):
    """/plan on via handle_turn sets PLAN_THEN_APPROVE mode."""
    from vnalpha.chat.modes import ExecutionMode

    ctrl, _ = _make_ctrl(in_memory_conn)
    ctrl.handle_turn("/plan on")
    assert ctrl.execution_mode == ExecutionMode.PLAN_THEN_APPROVE
