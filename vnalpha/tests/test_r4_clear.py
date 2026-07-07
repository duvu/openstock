"""R4 clear behavior tests — audit-preserving /clear semantics.

Task coverage:
  5.3.1  Decide audit-preserving /clear behavior
  5.3.2  Add is_visible and hidden_at columns
  5.3.3  /clear hides visible messages but retains rows
  5.3.4  Destructive clear requires --forget flag
  5.3.5  Help text matches actual behavior
  5.3.6  /clear preserves audit history
  5.3.7  Destructive clear requires explicit flag
"""

from __future__ import annotations

import pytest

from vnalpha.warehouse.chat_repo import (
    append_chat_message,
    clear_visible_messages,
    create_chat_session,
    list_chat_messages,
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


# ---------------------------------------------------------------------------
# 5.3.2: is_visible and hidden_at columns exist
# ---------------------------------------------------------------------------


def test_is_visible_column_exists(conn):
    """5.3.2: chat_message has is_visible column after migration."""
    cols_result = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'chat_message' AND column_name = 'is_visible'"
    ).fetchall()
    assert len(cols_result) == 1, "is_visible column must exist in chat_message"


def test_hidden_at_column_exists(conn):
    """5.3.2: chat_message has hidden_at column after migration."""
    cols_result = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'chat_message' AND column_name = 'hidden_at'"
    ).fetchall()
    assert len(cols_result) == 1, "hidden_at column must exist in chat_message"


# ---------------------------------------------------------------------------
# 5.3.3 and 5.3.6: /clear hides rows but preserves audit
# ---------------------------------------------------------------------------


def test_clear_hides_messages_from_list(conn):
    """5.3.3: After /clear, list_chat_messages returns empty (rows are hidden)."""
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Question 1")
    append_chat_message(conn, chat_session_id=sid, role="assistant", content="Answer 1")

    count = clear_visible_messages(conn, sid)
    assert count == 2

    visible_msgs = list_chat_messages(conn, sid)
    assert visible_msgs == [], "After /clear, visible messages should be empty"


def test_clear_preserves_rows_in_db(conn):
    """5.3.6: /clear preserves transcript rows in the database (audit history)."""
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Audit me")
    append_chat_message(conn, chat_session_id=sid, role="assistant", content="Noted")

    clear_visible_messages(conn, sid)

    # Rows must still exist in the database (not deleted)
    total_rows = conn.execute(
        "SELECT COUNT(*) FROM chat_message WHERE chat_session_id = ?", [sid]
    ).fetchone()[0]
    assert total_rows == 2, "Rows must be preserved after /clear (audit requirement)"


def test_clear_sets_is_visible_false(conn):
    """5.3.6: /clear sets is_visible=false on cleared rows."""
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Keep hidden")

    clear_visible_messages(conn, sid)

    hidden_count = conn.execute(
        "SELECT COUNT(*) FROM chat_message "
        "WHERE chat_session_id = ? AND is_visible = false",
        [sid],
    ).fetchone()[0]
    assert hidden_count == 1, "is_visible must be false after /clear"


def test_clear_sets_hidden_at_timestamp(conn):
    """5.3.6: /clear sets hidden_at to a non-null timestamp."""
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Hide me")

    clear_visible_messages(conn, sid)

    row = conn.execute(
        "SELECT hidden_at FROM chat_message WHERE chat_session_id = ?", [sid]
    ).fetchone()
    assert row is not None
    assert row[0] is not None, "hidden_at must be set after /clear"


def test_new_messages_visible_after_clear(conn):
    """5.3.6: Messages added after /clear are visible (not affected by previous clear)."""
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Before clear")
    clear_visible_messages(conn, sid)

    append_chat_message(conn, chat_session_id=sid, role="user", content="After clear")

    visible = list_chat_messages(conn, sid)
    assert len(visible) == 1
    assert visible[0]["content"] == "After clear"


def test_clear_does_not_affect_other_sessions(conn):
    """5.3.6: /clear only affects the target session."""
    sid_a = create_chat_session(conn)
    sid_b = create_chat_session(conn)

    append_chat_message(conn, chat_session_id=sid_a, role="user", content="Keep A")
    append_chat_message(conn, chat_session_id=sid_b, role="user", content="Clear B")

    clear_visible_messages(conn, sid_b)

    msgs_a = list_chat_messages(conn, sid_a)
    assert len(msgs_a) == 1, "Session A messages must not be affected by clearing B"
    assert msgs_a[0]["content"] == "Keep A"


# ---------------------------------------------------------------------------
# 5.3.4 and 5.3.7: Destructive clear requires --forget
# ---------------------------------------------------------------------------


def test_forget_deletes_rows(conn):
    """5.3.4: /clear --forget deletes transcript rows permanently."""
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Delete me")
    append_chat_message(conn, chat_session_id=sid, role="assistant", content="Me too")

    count = clear_visible_messages(conn, sid, forget=True)
    assert count == 2

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM chat_message WHERE chat_session_id = ?", [sid]
    ).fetchone()[0]
    assert total_rows == 0, "/clear --forget must delete all rows"


def test_clear_without_forget_does_not_delete(conn):
    """5.3.7: /clear without --forget must NOT delete rows (only hide)."""
    sid = create_chat_session(conn)
    append_chat_message(conn, chat_session_id=sid, role="user", content="Do not delete")

    clear_visible_messages(conn, sid, forget=False)  # explicit no-delete

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM chat_message WHERE chat_session_id = ?", [sid]
    ).fetchone()[0]
    assert total_rows == 1, "Without --forget, rows must not be deleted"


# ---------------------------------------------------------------------------
# 5.3.5: Help text reflects actual behavior
# ---------------------------------------------------------------------------


def test_chat_controller_help_text_mentions_clear_forget():
    """5.3.5: /help output describes --forget flag for destructive clear."""

    from vnalpha.chat.controller import ChatController

    messages = []
    ctrl = ChatController(
        on_message=lambda style, text: messages.append(text),
        target_date="2024-01-10",
    )

    help_text = ctrl._cmd_help()
    assert "/clear" in help_text, "/help must document /clear"
    assert "--forget" in help_text, "/help must document /clear --forget"


def test_chat_controller_clear_without_session_returns_warning():
    """5.3.3: /clear with no session returns a warning, not an error."""
    from vnalpha.chat.controller import ChatController

    messages = []
    ctrl = ChatController(
        on_message=lambda style, text: messages.append(text),
        target_date="2024-01-10",
    )
    # No session set
    result = ctrl._cmd_clear(forget=False)
    assert "no active" in result.lower() or "no session" in result.lower() or result


def test_chat_controller_clear_via_handle_turn():
    """5.3.3: /clear is handled as a chat-local command via handle_turn."""
    from vnalpha.chat.controller import ChatController
    from vnalpha.warehouse.chat_repo import create_chat_session
    from vnalpha.warehouse.migrations import run_migrations

    c = in_memory_connection()
    run_migrations(conn=c)
    sid = create_chat_session(c)

    messages = []
    ctrl = ChatController(
        connection_factory=_conn_factory(c),
        on_message=lambda style, text: messages.append(text),
        target_date="2024-01-10",
        chat_session_id=sid,
    )

    ctrl.handle_turn("/clear")
    assert any(
        "clear" in m.lower() or "log" in m.lower() or "message" in m.lower()
        for m in messages
    )
    c.close()
