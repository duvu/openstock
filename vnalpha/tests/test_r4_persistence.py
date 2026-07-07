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
    list_trace_events_for_session,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


def test_persist_user_prompt(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn, chat_session_id=sid, role="user", content="Show VNM analysis"
    )
    msgs = list_chat_messages(conn, sid)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Show VNM analysis"


def test_persist_assistant_answer(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="VNM looks bullish",
        message_type="answer",
    )
    msgs = list_chat_messages(conn, sid)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["message_type"] == "answer"


def test_persist_assistant_refusal(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="Refused: trading not allowed",
        message_type="refusal",
    )
    msgs = list_chat_messages(conn, sid)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["message_type"] == "refusal"
    assert "trading" in msgs[0]["content"]


def test_persist_slash_command_input(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="user",
        content="/scan --date 2024-01-01",
        message_type="slash_command",
    )
    msgs = list_chat_messages(conn, sid)
    assert len(msgs) == 1
    assert msgs[0]["message_type"] == "slash_command"


def test_persist_slash_command_result(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="Scan complete: 3 candidates",
        message_type="slash_command_result",
        research_session_id="res-123",
    )
    msgs = list_chat_messages(conn, sid)
    assert len(msgs) == 1
    assert msgs[0]["message_type"] == "slash_command_result"
    assert msgs[0]["research_session_id"] == "res-123"


def test_persist_chat_local_command_input(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="user",
        content="/clear",
        message_type="chat_local_command",
    )
    msgs = list_chat_messages(conn, sid)
    assert any(m["message_type"] == "chat_local_command" for m in msgs)


def test_persist_plan_preview_with_plan_json(conn):
    import json

    sid = create_chat_session(conn)
    plan_data = {"intent": "scan_candidates", "steps": [{"tool": "watchlist.scan"}]}
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="Plan preview: scan candidates",
        message_type="plan_preview",
        plan_json=json.dumps(plan_data),
    )
    msgs = list_chat_messages(conn, sid)
    assert len(msgs) == 1
    assert msgs[0]["message_type"] == "plan_preview"
    stored_plan = json.loads(msgs[0]["plan_json"])
    assert stored_plan["intent"] == "scan_candidates"


def test_persist_plan_approval(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="user",
        content="Approved",
        message_type="plan_approval",
    )
    msgs = list_chat_messages(conn, sid)
    assert any(m["message_type"] == "plan_approval" for m in msgs)


def test_persist_plan_cancellation(conn):
    sid = create_chat_session(conn)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="user",
        content="Cancelled",
        message_type="plan_cancel",
    )
    msgs = list_chat_messages(conn, sid)
    assert any(m["message_type"] == "plan_cancel" for m in msgs)


def test_persist_trace_event(conn):
    sid = create_chat_session(conn)
    append_trace_event(
        conn,
        chat_session_id=sid,
        tool_name="watchlist.scan",
        status="SUCCESS",
        elapsed_ms=42.0,
        tool_trace_id="trace-001",
    )
    events = list_trace_events_for_session(conn, sid)
    assert len(events) == 1
    assert events[0]["role"] == "trace"
    assert events[0]["message_type"] == "tool_trace_event"
    assert "watchlist.scan" in events[0]["content"]


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
