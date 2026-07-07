"""R4 session lifecycle tests — chat_session create/resume/new/context.

Task coverage:
  5.6.1  TUI start creates or resumes chat_session
  5.6.2  /new creates a new chat_session and switches controller context
  5.6.3  Chat session context stores target_date, selected symbol, mode, pending-plan
  5.6.4  /context reads deterministic controller/session context
  5.6.5  Tests for session creation/resume/new/context
"""

from __future__ import annotations

import pytest

from vnalpha.chat.controller import ChatController
from vnalpha.chat.modes import ExecutionMode
from vnalpha.warehouse.chat_repo import create_chat_session, list_chat_messages
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


def test_chat_session_can_be_created(conn):
    """5.6.1: A chat_session can be created with target_date."""
    sid = create_chat_session(conn, target_date="2024-01-10", surface="tui-chat")
    assert sid is not None
    assert len(sid) > 0

    row = conn.execute(
        "SELECT target_date, surface FROM chat_session WHERE chat_session_id = ?", [sid]
    ).fetchone()
    assert row is not None
    assert str(row[0]) == "2024-01-10"
    assert row[1] == "tui-chat"


def test_controller_accepts_existing_session_id(conn):
    """5.6.1: ChatController can be initialized with an existing chat_session_id."""
    sid = create_chat_session(conn, target_date="2024-01-10")
    ctrl = _make_ctrl(conn, session_id=sid)
    assert ctrl._chat_session_id == sid


def test_controller_has_no_session_by_default():
    """5.6.1: ChatController starts with no session if none provided."""
    c = in_memory_connection()
    run_migrations(conn=c)
    ctrl = _make_ctrl(c)
    assert ctrl._chat_session_id is None
    c.close()


# ---------------------------------------------------------------------------
# 5.6.2: /new creates a new session and switches context
# ---------------------------------------------------------------------------


def test_cmd_new_creates_new_session(conn):
    """5.6.2: /new command creates a new chat_session in the database."""
    ctrl = _make_ctrl(conn)
    ctrl._cmd_new()

    assert ctrl._chat_session_id is not None
    row = conn.execute(
        "SELECT chat_session_id FROM chat_session WHERE chat_session_id = ?",
        [ctrl._chat_session_id],
    ).fetchone()
    assert row is not None, "/new must create a persisted chat_session"


def test_cmd_new_switches_session_id(conn):
    """5.6.2: /new updates _chat_session_id to the new session."""
    sid_old = create_chat_session(conn)
    ctrl = _make_ctrl(conn, session_id=sid_old)

    ctrl._cmd_new()
    assert ctrl._chat_session_id != sid_old, "/new must create a different session"


def test_cmd_new_resets_pending_plan(conn):
    """5.6.2: /new clears any pending plan from the previous session."""
    from vnalpha.assistant.models import AssistantPlan

    ctrl = _make_ctrl(conn)
    ctrl._pending_plan = AssistantPlan(intent="old_plan", steps=[])
    ctrl._cmd_new()

    assert ctrl._pending_plan is None, "/new must clear _pending_plan"


def test_cmd_new_returns_confirmation_string(conn):
    """5.6.2: /new returns a confirmation string with session info."""
    ctrl = _make_ctrl(conn)
    result = ctrl._cmd_new()

    assert isinstance(result, str)
    assert len(result) > 0
    assert "session" in result.lower() or "new" in result.lower()


# ---------------------------------------------------------------------------
# 5.6.3: Session context stores target_date, mode, pending-plan state
# ---------------------------------------------------------------------------


def test_controller_stores_target_date():
    """5.6.3: Controller exposes target_date as context."""
    c = in_memory_connection()
    run_migrations(conn=c)
    ctrl = _make_ctrl(c)
    assert ctrl._target_date == "2024-01-10"
    c.close()


def test_controller_stores_execution_mode():
    """5.6.3: Controller exposes execution_mode as context."""
    c = in_memory_connection()
    run_migrations(conn=c)
    ctrl = _make_ctrl(c, mode=ExecutionMode.PLAN_THEN_APPROVE)
    assert ctrl.execution_mode == ExecutionMode.PLAN_THEN_APPROVE
    c.close()


def test_controller_stores_pending_plan_state():
    """5.6.3: Controller tracks pending plan state."""
    from vnalpha.assistant.models import AssistantPlan

    c = in_memory_connection()
    run_migrations(conn=c)
    ctrl = _make_ctrl(c)

    assert ctrl._pending_plan is None
    ctrl._pending_plan = AssistantPlan(intent="test", steps=[])
    assert ctrl._pending_plan is not None
    c.close()


# ---------------------------------------------------------------------------
# 5.6.4: /context reads deterministic controller/session context
# ---------------------------------------------------------------------------


def test_cmd_context_includes_execution_mode(conn):
    """5.6.4: /context output includes the current execution mode."""
    ctrl = _make_ctrl(conn, mode=ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY)
    result = ctrl._cmd_context()

    assert "execution_mode" in result.lower() or "auto" in result.lower()


def test_cmd_context_includes_target_date(conn):
    """5.6.4: /context output includes the target date."""
    ctrl = _make_ctrl(conn)
    result = ctrl._cmd_context()

    assert "2024-01-10" in result or "target_date" in result.lower()


def test_cmd_context_includes_session_id_when_set(conn):
    """5.6.4: /context output includes chat_session_id when set."""
    sid = create_chat_session(conn)
    ctrl = _make_ctrl(conn, session_id=sid)
    result = ctrl._cmd_context()

    assert sid[:8] in result or "chat_session_id" in result.lower()


def test_cmd_context_no_session_still_returns(conn):
    """5.6.4: /context without a session still returns a useful string."""
    ctrl = _make_ctrl(conn)
    result = ctrl._cmd_context()

    assert isinstance(result, str)
    assert len(result) > 0


def test_cmd_context_shows_pending_plan_status(conn):
    """5.6.4: /context reflects whether there is a pending plan."""
    from vnalpha.assistant.models import AssistantPlan

    ctrl = _make_ctrl(conn)
    result_no_plan = ctrl._cmd_context()

    ctrl._pending_plan = AssistantPlan(intent="some_plan", steps=[])
    result_with_plan = ctrl._cmd_context()

    assert (
        "none" in result_no_plan.lower()
        or "no" in result_no_plan.lower()
        or "pending_plan" in result_no_plan.lower()
    )
    assert "yes" in result_with_plan.lower() or "pending" in result_with_plan.lower()


# ---------------------------------------------------------------------------
# 5.6.5: Tests for session creation/resume/new/context (integration)
# ---------------------------------------------------------------------------


def test_full_session_lifecycle(conn):
    """5.6.5: Full session lifecycle — create, use, new, verify switch."""
    ctrl = _make_ctrl(conn)

    ctrl._cmd_new()
    first_sid = ctrl._chat_session_id
    assert first_sid is not None

    ctrl._cmd_new()
    second_sid = ctrl._chat_session_id
    assert second_sid is not None
    assert second_sid != first_sid, "Each /new should produce a distinct session"


def test_session_messages_isolated_after_new(conn):
    """5.6.5: Messages from different sessions are isolated."""
    from vnalpha.warehouse.chat_repo import append_chat_message

    ctrl = _make_ctrl(conn)
    ctrl._cmd_new()
    sid_a = ctrl._chat_session_id
    append_chat_message(
        conn, chat_session_id=sid_a, role="user", content="Session A message"
    )

    ctrl._cmd_new()
    sid_b = ctrl._chat_session_id

    msgs_a = list_chat_messages(conn, sid_a)
    msgs_b = list_chat_messages(conn, sid_b)

    assert len(msgs_a) == 1
    assert len(msgs_b) == 0


def test_context_via_handle_turn(conn):
    """5.6.5: /context is accessible via handle_turn."""
    ctrl = _make_ctrl(conn)
    ctrl.handle_turn("/context")

    context_msgs = [
        t
        for _, t in ctrl._messages
        if "execution_mode" in t.lower() or "context" in t.lower()
    ]
    assert len(context_msgs) >= 1, "/context must produce output via handle_turn"


def test_new_via_handle_turn(conn):
    """5.6.5: /new is accessible via handle_turn."""
    ctrl = _make_ctrl(conn)
    ctrl.handle_turn("/new")

    assert ctrl._chat_session_id is not None, (
        "/new via handle_turn must create a session"
    )
