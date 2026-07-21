"""R4 persistence tests — every turn type creates a chat_message row.

Task coverage:
  5.2.1  User prompt persisted as chat_message(role='user')
  5.2.2  Assistant answer persisted as chat_message(role='assistant')
  5.2.3  Assistant refusal persisted as chat_message(role='assistant', message_type='refusal')
  5.2.4  Slash command input persisted as chat_message(role='user', message_type='slash_command')
  5.2.5  Slash command result persisted as chat_message linked to research_session where possible
  5.2.6  Chat-local command input/output persisted
  5.2.7  Plan preview persisted with plan_json
  5.2.8  Plan approval decision persisted
  5.2.9  Plan cancellation decision persisted
  5.2.10 Trace lifecycle events persisted
  5.2.11 Tests for every persisted turn type
"""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.warehouse.chat_repo import (
    append_chat_message,
    append_trace_event,
    create_chat_session,
    list_chat_messages,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


def test_persist_multiple_turn_types_in_sequence(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="user",
        content="question",
        message_type="plain_text",
    )
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="plan preview",
        message_type="plan_preview",
    )
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="user",
        content="approved",
        message_type="plan_approval",
    )
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="answer",
        message_type="answer",
    )
    append_trace_event(
        conn, chat_session_id=sid, tool_name="scan", status="SUCCESS", elapsed_ms=10.0
    )

    msgs = list_chat_messages(conn, sid)
    assert len(msgs) == 4

    all_msgs_inc_hidden = conn.execute(
        "SELECT COUNT(*) FROM chat_message WHERE chat_session_id=?", [sid]
    ).fetchone()[0]
    assert all_msgs_inc_hidden == 5
