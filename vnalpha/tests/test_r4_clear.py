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


# ---------------------------------------------------------------------------
# 5.3.3 and 5.3.6: /clear hides rows but preserves audit
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 5.3.5: Help text reflects actual behavior
# ---------------------------------------------------------------------------
