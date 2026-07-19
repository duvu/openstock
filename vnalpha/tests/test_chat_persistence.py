"""Tests for Phase 5.10 chat persistence (chat_session + chat_message)."""

from __future__ import annotations

import json
import time

import duckdb
import pytest

from vnalpha.warehouse.chat_repo import (
    append_chat_message,
    clear_visible_messages,
    create_chat_session,
    finish_chat_session,
    list_chat_messages,
    update_chat_session_context,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Schema creation tests
# ---------------------------------------------------------------------------


def test_migrations_create_chat_tables(conn):
    tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
    assert "chat_session" in tables
    assert "chat_message" in tables


def test_migrations_idempotent_with_chat_tables(conn):
    """Running migrations a second time should not raise."""
    run_migrations(conn=conn)
    tables = conn.execute("SHOW TABLES").fetchall()
    assert len(tables) >= 2  # at minimum chat_session and chat_message are present


# ---------------------------------------------------------------------------
# chat_session tests
# ---------------------------------------------------------------------------


def test_create_chat_session_returns_uuid(conn):
    sid = create_chat_session(conn)
    assert isinstance(sid, str)
    assert len(sid) == 36  # UUID4 string form


def test_create_chat_session_defaults(conn):
    sid = create_chat_session(conn)
    row = conn.execute(
        "SELECT status, surface FROM chat_session WHERE chat_session_id = ?", [sid]
    ).fetchone()
    assert row is not None
    status, surface = row
    assert status == "active"
    assert surface == "tui-chat"


def test_create_chat_session_custom_params(conn):
    sid = create_chat_session(
        conn, surface="cli", target_date="2026-07-07", title="Morning scan"
    )
    row = conn.execute(
        "SELECT surface, target_date, title FROM chat_session WHERE chat_session_id = ?",
        [sid],
    ).fetchone()
    assert row is not None
    surface, target_date, title = row
    assert surface == "cli"
    assert target_date == "2026-07-07"
    assert title == "Morning scan"


def test_finish_chat_session(conn):
    sid = create_chat_session(conn)
    finish_chat_session(conn, sid)
    row = conn.execute(
        "SELECT status, updated_at FROM chat_session WHERE chat_session_id = ?", [sid]
    ).fetchone()
    assert row is not None
    status, updated_at = row
    assert status == "finished"
    assert updated_at is not None


def test_update_chat_session_context(conn):
    sid = create_chat_session(conn)
    ctx = json.dumps({"symbol": "VNM", "date": "2026-07-07"})
    update_chat_session_context(conn, sid, ctx)
    row = conn.execute(
        "SELECT context_json FROM chat_session WHERE chat_session_id = ?", [sid]
    ).fetchone()
    assert row is not None
    stored = row[0]
    assert stored == ctx


def test_chat_json_fields_are_structurally_redacted(conn):
    sid = create_chat_session(conn)
    private_fragment = "SESSION_SECRET_123"
    control = "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"
    hostile = json.dumps(
        {
            "session_id": private_fragment,
            "nested": {"message": control},
        }
    )

    update_chat_session_context(conn, sid, hostile)
    mid = append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="safe",
        tool_trace_ids_json=hostile,
        plan_json=hostile,
        metadata_json=hostile,
    )

    context_json = conn.execute(
        "SELECT context_json FROM chat_session WHERE chat_session_id = ?", [sid]
    ).fetchone()[0]
    row = conn.execute(
        "SELECT tool_trace_ids_json, plan_json, metadata_json "
        "FROM chat_message WHERE chat_message_id = ?",
        [mid],
    ).fetchone()
    decoded = [json.loads(value) for value in (context_json, *row)]
    assert all(value["session_id"] == "[REDACTED]" for value in decoded)
    assert all("\x1b]8;" not in value["nested"]["message"] for value in decoded)


def test_chat_json_fields_reject_malformed_json(conn):
    sid = create_chat_session(conn)

    with pytest.raises(ValueError, match="metadata_json must be valid JSON"):
        append_chat_message(
            conn,
            chat_session_id=sid,
            role="assistant",
            content="safe",
            metadata_json="{not-json password=PRIVATE_FRAGMENT}",
        )

    assert conn.execute("SELECT COUNT(*) FROM chat_message").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# chat_message tests
# ---------------------------------------------------------------------------


def test_append_chat_message_returns_uuid(conn):
    sid = create_chat_session(conn)
    mid = append_chat_message(conn, chat_session_id=sid, role="user", content="Hello")
    assert isinstance(mid, str)
    assert len(mid) == 36


def test_append_chat_message_defaults(conn):
    sid = create_chat_session(conn)
    mid = append_chat_message(conn, chat_session_id=sid, role="user", content="Hi")
    row = conn.execute(
        "SELECT role, content, message_type FROM chat_message WHERE chat_message_id = ?",
        [mid],
    ).fetchone()
    assert row is not None
    role, content, message_type = row
    assert role == "user"
    assert content == "Hi"
    assert message_type == "plain_text"


def test_append_chat_message_optional_fields(conn):
    sid = create_chat_session(conn)
    mid = append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="Analysis complete.",
        message_type="assistant_answer",
        assistant_session_id="asst-123",
        metadata_json='{"tokens": 42}',
    )
    row = conn.execute(
        """
        SELECT message_type, assistant_session_id, metadata_json
        FROM chat_message WHERE chat_message_id = ?
        """,
        [mid],
    ).fetchone()
    assert row is not None
    message_type, assistant_session_id, metadata_json = row
    assert message_type == "assistant_answer"
    assert assistant_session_id == "asst-123"
    assert metadata_json == '{"tokens": 42}'


# ---------------------------------------------------------------------------
# list_chat_messages ordering tests
# ---------------------------------------------------------------------------


def test_list_chat_messages_empty(conn):
    sid = create_chat_session(conn)
    messages = list_chat_messages(conn, sid)
    assert messages == []


def test_list_chat_messages_returns_dicts(conn):
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Ping")
    messages = list_chat_messages(conn, sid)
    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, dict)
    assert msg["role"] == "user"
    assert msg["content"] == "Ping"
    assert msg["chat_session_id"] == sid


def test_list_chat_messages_ordered_asc(conn):
    """Messages must be returned in created_at ASC order."""
    sid = create_chat_session(conn)
    roles = ["user", "assistant", "user", "assistant"]
    contents = ["Q1", "A1", "Q2", "A2"]
    for role, content in zip(roles, contents, strict=True):
        append_chat_message(conn, chat_session_id=sid, role=role, content=content)
        # tiny sleep to ensure distinct timestamps
        time.sleep(0.01)

    messages = list_chat_messages(conn, sid)
    assert len(messages) == 4
    assert [m["content"] for m in messages] == ["Q1", "A1", "Q2", "A2"]


def test_list_chat_messages_isolated_by_session(conn):
    """Messages from different sessions must not bleed into each other."""
    sid_a = create_chat_session(conn)
    sid_b = create_chat_session(conn)
    append_chat_message(
        conn, chat_session_id=sid_a, role="user", content="Session A msg"
    )
    append_chat_message(
        conn, chat_session_id=sid_b, role="user", content="Session B msg"
    )

    msgs_a = list_chat_messages(conn, sid_a)
    msgs_b = list_chat_messages(conn, sid_b)
    assert len(msgs_a) == 1
    assert msgs_a[0]["content"] == "Session A msg"
    assert len(msgs_b) == 1
    assert msgs_b[0]["content"] == "Session B msg"


# ---------------------------------------------------------------------------
# clear_visible_messages tests
# ---------------------------------------------------------------------------


def test_clear_visible_messages_returns_count(conn):
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="A")
    append_chat_message(conn, chat_session_id=sid, role="assistant", content="B")
    count = clear_visible_messages(conn, sid)
    assert count == 2


def test_clear_visible_messages_removes_all(conn):
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="X")
    clear_visible_messages(conn, sid)
    messages = list_chat_messages(conn, sid)
    assert messages == []


def test_clear_visible_messages_zero_when_empty(conn):
    sid = create_chat_session(conn)
    count = clear_visible_messages(conn, sid)
    assert count == 0


def test_clear_visible_messages_only_affects_target_session(conn):
    sid_a = create_chat_session(conn)
    sid_b = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid_a, role="user", content="Keep me")
    append_chat_message(conn, chat_session_id=sid_b, role="user", content="Delete me")

    clear_visible_messages(conn, sid_b)

    assert len(list_chat_messages(conn, sid_a)) == 1
    assert len(list_chat_messages(conn, sid_b)) == 0


# ---------------------------------------------------------------------------
# Full transcript test
# ---------------------------------------------------------------------------


def test_full_chat_transcript_workflow(conn):
    """End-to-end: create session, append multi-role messages, list, finish."""
    sid = create_chat_session(conn, title="E2E test session")

    append_chat_message(
        conn, chat_session_id=sid, role="system", content="You are helpful."
    )
    time.sleep(0.01)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Analyse VNM")
    time.sleep(0.01)
    append_chat_message(
        conn,
        chat_session_id=sid,
        role="assistant",
        content="VNM shows bullish structure.",
        message_type="assistant_answer",
    )

    messages = list_chat_messages(conn, sid)
    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["message_type"] == "assistant_answer"

    finish_chat_session(conn, sid)
    row = conn.execute(
        "SELECT status FROM chat_session WHERE chat_session_id = ?", [sid]
    ).fetchone()
    assert row[0] == "finished"
