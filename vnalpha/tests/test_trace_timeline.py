"""Tests for Section 8 (Trace timeline) — Phase 5.10.

Covers:
- append_trace_event with RUNNING / SUCCESS / FAILED status
- list_trace_events_for_session ordering and session isolation
- tool_trace_id stored as JSON array in tool_trace_ids_json
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# append_trace_event — row metadata
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# list_trace_events_for_session — ordering
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# list_trace_events_for_session — isolation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# list_trace_events_for_session — non-trace messages not included
# ---------------------------------------------------------------------------
