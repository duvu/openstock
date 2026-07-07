"""Tests for Section 8 (Trace timeline) — Phase 5.10.

Covers:
- append_trace_event with RUNNING / SUCCESS / FAILED status
- list_trace_events_for_session ordering and session isolation
- tool_trace_id stored as JSON array in tool_trace_ids_json
"""

from __future__ import annotations

import json
import time

import pytest

from vnalpha.warehouse.chat_repo import (
    append_trace_event,
    create_chat_session,
    list_trace_events_for_session,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


def _make_session(conn) -> str:
    return create_chat_session(conn, surface="test")


# ---------------------------------------------------------------------------
# append_trace_event — content formatting
# ---------------------------------------------------------------------------


def test_running_content(conn):
    """RUNNING status → '⟳ tool_name running...'"""
    sid = _make_session(conn)
    append_trace_event(conn, chat_session_id=sid, tool_name="my_tool", status="RUNNING")
    events = list_trace_events_for_session(conn, sid)
    assert len(events) == 1
    assert events[0]["content"] == "\u27f3 my_tool running..."


def test_success_content(conn):
    """SUCCESS status → '✓ tool_name success 42ms'"""
    sid = _make_session(conn)
    append_trace_event(
        conn,
        chat_session_id=sid,
        tool_name="fast_tool",
        status="SUCCESS",
        elapsed_ms=42.7,
    )
    events = list_trace_events_for_session(conn, sid)
    assert len(events) == 1
    assert events[0]["content"] == "\u2713 fast_tool success 42ms"


def test_failed_content(conn):
    """FAILED status → '✗ tool_name failed 18ms'"""
    sid = _make_session(conn)
    append_trace_event(
        conn,
        chat_session_id=sid,
        tool_name="bad_tool",
        status="FAILED",
        elapsed_ms=18.0,
    )
    events = list_trace_events_for_session(conn, sid)
    assert len(events) == 1
    assert events[0]["content"] == "\u2717 bad_tool failed 18ms"


# ---------------------------------------------------------------------------
# append_trace_event — row metadata
# ---------------------------------------------------------------------------


def test_trace_event_role_and_type(conn):
    """Inserted row has role='trace' and message_type='tool_trace_event'."""
    sid = _make_session(conn)
    append_trace_event(conn, chat_session_id=sid, tool_name="t", status="RUNNING")
    events = list_trace_events_for_session(conn, sid)
    assert events[0]["role"] == "trace"
    assert events[0]["message_type"] == "tool_trace_event"


def test_tool_trace_id_stored_as_json_array(conn):
    """tool_trace_id is serialised as a JSON array in tool_trace_ids_json."""
    sid = _make_session(conn)
    trace_id = "tt-abc-123"
    append_trace_event(
        conn,
        chat_session_id=sid,
        tool_name="tool_with_trace",
        status="SUCCESS",
        elapsed_ms=10,
        tool_trace_id=trace_id,
    )
    events = list_trace_events_for_session(conn, sid)
    assert events[0]["tool_trace_ids_json"] == json.dumps([trace_id])


def test_tool_trace_id_none_stores_null(conn):
    """When tool_trace_id is None, tool_trace_ids_json should be NULL/None."""
    sid = _make_session(conn)
    append_trace_event(conn, chat_session_id=sid, tool_name="anon", status="RUNNING")
    events = list_trace_events_for_session(conn, sid)
    assert events[0]["tool_trace_ids_json"] is None


# ---------------------------------------------------------------------------
# list_trace_events_for_session — ordering
# ---------------------------------------------------------------------------


def test_list_trace_events_ordered_by_created_at(conn):
    """Events are returned in ascending created_at order."""
    sid = _make_session(conn)
    append_trace_event(conn, chat_session_id=sid, tool_name="first", status="RUNNING")
    time.sleep(0.01)
    append_trace_event(
        conn, chat_session_id=sid, tool_name="second", status="SUCCESS", elapsed_ms=5
    )
    time.sleep(0.01)
    append_trace_event(
        conn, chat_session_id=sid, tool_name="third", status="FAILED", elapsed_ms=3
    )

    events = list_trace_events_for_session(conn, sid)
    assert len(events) == 3
    tool_names = [e["content"].split()[1] for e in events]
    assert tool_names == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# list_trace_events_for_session — isolation
# ---------------------------------------------------------------------------


def test_list_trace_events_isolated_by_session(conn):
    """Events from other sessions are NOT returned."""
    sid_a = _make_session(conn)
    sid_b = _make_session(conn)

    append_trace_event(
        conn, chat_session_id=sid_a, tool_name="tool_a", status="RUNNING"
    )
    append_trace_event(
        conn, chat_session_id=sid_b, tool_name="tool_b", status="SUCCESS", elapsed_ms=9
    )

    events_a = list_trace_events_for_session(conn, sid_a)
    events_b = list_trace_events_for_session(conn, sid_b)

    assert len(events_a) == 1
    assert "\u27f3 tool_a running..." == events_a[0]["content"]

    assert len(events_b) == 1
    assert "\u2713 tool_b success 9ms" == events_b[0]["content"]


def test_list_trace_events_empty_for_unknown_session(conn):
    """Returns empty list for a session that has no trace events."""
    events = list_trace_events_for_session(conn, "nonexistent-session-id")
    assert events == []


# ---------------------------------------------------------------------------
# list_trace_events_for_session — non-trace messages not included
# ---------------------------------------------------------------------------


def test_list_trace_events_excludes_plain_messages(conn):
    """plain_text messages in the same session are NOT returned by the helper."""
    from vnalpha.warehouse.chat_repo import append_chat_message

    sid = _make_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Hello")
    append_trace_event(conn, chat_session_id=sid, tool_name="mytool", status="RUNNING")

    events = list_trace_events_for_session(conn, sid)
    assert len(events) == 1
    assert events[0]["message_type"] == "tool_trace_event"
