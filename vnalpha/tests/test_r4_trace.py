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
    append_trace_event,
    create_chat_session,
    list_trace_events_for_session,
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


def test_trace_callback_persists_running_event(conn, session_id):
    """5.5.1: Trace callback stores RUNNING event in chat_message when session active."""
    ctrl = _make_ctrl(conn, session_id=session_id)

    from vnalpha.tools.executor import TraceEvent

    event = TraceEvent(
        tool_name="watchlist.scan", status="RUNNING", duration_ms=None, tool_trace_id=""
    )
    ctrl._on_trace(event)

    events = list_trace_events_for_session(conn, session_id)
    assert len(events) == 1
    assert "watchlist.scan" in events[0]["content"]


def test_trace_callback_persists_success_event(conn, session_id):
    """5.5.1: Trace callback stores SUCCESS event with duration in chat_message."""
    ctrl = _make_ctrl(conn, session_id=session_id)

    from vnalpha.tools.executor import TraceEvent

    event = TraceEvent(
        tool_name="features.query",
        status="SUCCESS",
        duration_ms=150.0,
        tool_trace_id="",
    )
    ctrl._on_trace(event)

    events = list_trace_events_for_session(conn, session_id)
    assert len(events) == 1
    assert "features.query" in events[0]["content"]
    assert "success" in events[0]["content"].lower()


def test_trace_callback_persists_failed_event(conn, session_id):
    """5.5.1: Trace callback stores FAILED event in chat_message."""
    ctrl = _make_ctrl(conn, session_id=session_id)

    from vnalpha.tools.executor import TraceEvent

    event = TraceEvent(
        tool_name="score.query", status="FAILED", duration_ms=25.0, tool_trace_id=""
    )
    ctrl._on_trace(event)

    events = list_trace_events_for_session(conn, session_id)
    assert len(events) == 1
    assert "score.query" in events[0]["content"]


def test_trace_callback_no_persist_without_session(conn):
    """5.5.1: Without a session_id, trace callback does not persist anything."""
    ctrl = _make_ctrl(conn, session_id=None)

    from vnalpha.tools.executor import TraceEvent

    event = TraceEvent(
        tool_name="watchlist.scan", status="SUCCESS", duration_ms=10.0, tool_trace_id=""
    )
    ctrl._on_trace(event)

    rows = conn.execute(
        "SELECT COUNT(*) FROM chat_message WHERE role='trace'"
    ).fetchone()[0]
    assert rows == 0, "No trace rows should be persisted without a session"


# ---------------------------------------------------------------------------
# 5.5.2: Trace events include required fields
# ---------------------------------------------------------------------------


def test_trace_event_includes_tool_name(conn, session_id):
    """5.5.2: Persisted trace event content includes the tool name."""

    append_trace_event(
        conn,
        chat_session_id=session_id,
        tool_name="my_tool",
        status="SUCCESS",
        elapsed_ms=99.0,
    )

    events = list_trace_events_for_session(conn, session_id)
    assert "my_tool" in events[0]["content"]


def test_trace_event_includes_status(conn, session_id):
    """5.5.2: Persisted trace event content includes the status."""

    append_trace_event(
        conn,
        chat_session_id=session_id,
        tool_name="my_tool",
        status="SUCCESS",
        elapsed_ms=42.0,
    )

    events = list_trace_events_for_session(conn, session_id)
    assert "success" in events[0]["content"].lower()


def test_trace_event_includes_duration(conn, session_id):
    """5.5.2: Persisted trace event content includes the duration in ms."""
    append_trace_event(
        conn,
        chat_session_id=session_id,
        tool_name="timed_tool",
        status="SUCCESS",
        elapsed_ms=77.0,
    )

    events = list_trace_events_for_session(conn, session_id)
    assert "77ms" in events[0]["content"]


def test_trace_event_includes_tool_trace_id(conn, session_id):
    """5.5.2: Persisted trace event stores tool_trace_id when provided."""
    import json

    trace_id = "ttrace-xyz-789"
    append_trace_event(
        conn,
        chat_session_id=session_id,
        tool_name="traced_tool",
        status="SUCCESS",
        elapsed_ms=5.0,
        tool_trace_id=trace_id,
    )

    events = list_trace_events_for_session(conn, session_id)
    stored_ids = json.loads(events[0]["tool_trace_ids_json"])
    assert trace_id in stored_ids


# ---------------------------------------------------------------------------
# 5.5.3: /trace reads persisted trace events for current session
# ---------------------------------------------------------------------------


def test_cmd_trace_reads_persisted_events(conn, session_id):
    """5.5.3: _cmd_trace returns content from persisted trace events."""
    append_trace_event(
        conn,
        chat_session_id=session_id,
        tool_name="scan_tool",
        status="SUCCESS",
        elapsed_ms=10.0,
    )

    ctrl = _make_ctrl(conn, session_id=session_id)
    result = ctrl._cmd_trace([])

    assert "scan_tool" in result, "/trace must include tool names from persisted events"
    assert "event" in result.lower() or "trace" in result.lower()


def test_cmd_trace_shows_multiple_events_in_order(conn, session_id):
    """5.5.3: /trace returns multiple events in chronological order."""
    import time

    append_trace_event(
        conn, chat_session_id=session_id, tool_name="first", status="RUNNING"
    )
    time.sleep(0.01)
    append_trace_event(
        conn,
        chat_session_id=session_id,
        tool_name="second",
        status="SUCCESS",
        elapsed_ms=5.0,
    )

    ctrl = _make_ctrl(conn, session_id=session_id)
    result = ctrl._cmd_trace([])

    first_pos = result.find("first")
    second_pos = result.find("second")
    assert first_pos < second_pos, "Events should appear in chronological order"


def test_cmd_trace_without_session_returns_useful_message():
    """5.5.4: /trace with no session returns a useful message (not empty/crash)."""
    c = in_memory_connection()
    run_migrations(conn=c)

    ctrl = _make_ctrl(c, session_id=None)
    result = ctrl._cmd_trace([])

    assert result is not None
    assert len(result) > 0
    assert "no" in result.lower() or "session" in result.lower()
    c.close()


# ---------------------------------------------------------------------------
# 5.5.4: Trace render shows useful output for no events
# ---------------------------------------------------------------------------


def test_cmd_trace_no_events_returns_useful_message(conn, session_id):
    """5.5.4: /trace with session but no events shows a useful message."""
    ctrl = _make_ctrl(conn, session_id=session_id)
    result = ctrl._cmd_trace([])

    assert result is not None
    assert len(result) > 0
    assert (
        "no trace" in result.lower()
        or "no event" in result.lower()
        or "0 event" in result.lower()
    )


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


def test_trace_events_from_multiple_tools(conn, session_id):
    """5.5.5: Multiple tool traces from a single session all appear in /trace output."""
    from vnalpha.tools.executor import TraceEvent

    ctrl = _make_ctrl(conn, session_id=session_id)

    for tool in ["tool_a", "tool_b", "tool_c"]:
        ctrl._on_trace(
            TraceEvent(
                tool_name=tool, status="SUCCESS", duration_ms=1.0, tool_trace_id=""
            )
        )

    result = ctrl._cmd_trace([])
    for tool in ["tool_a", "tool_b", "tool_c"]:
        assert tool in result, f"{tool} must appear in /trace output"
