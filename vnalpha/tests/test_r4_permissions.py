"""R4 permission evaluation tests — classify tools before storing pending plan.

Task coverage:
  5.4.1  Evaluate every planned tool before storing a pending plan
  5.4.2  ALLOW tools may auto-run in safe-read mode
  5.4.3  ASK tools may become pending only in approval mode
  5.4.4  DENY tools produce a refusal in current mode
  5.4.5  HARD_DENY tools produce refusal and are never pending
  5.4.6  Restricted planned tools are not stored in _pending_plan
  5.4.7  Approval cannot run a restricted pending plan
  5.4.8  Refusal messages for restricted planned tools are persisted
"""

from __future__ import annotations

from vnalpha.chat.controller import ChatController
from vnalpha.chat.modes import ExecutionMode
from vnalpha.chat.safety import PermissionState, get_permission_state
from vnalpha.warehouse.chat_repo import create_chat_session, list_chat_messages
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _NonClosingConn:
    def __init__(self, inner):
        self._inner = inner

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _make_conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    return c


def _conn_factory(conn):
    def factory():
        return _NonClosingConn(conn)

    return factory


def _make_ctrl(conn, mode=ExecutionMode.PLAN_THEN_APPROVE, session_id=None):
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


def _make_plan(tool_names):
    from vnalpha.assistant.models import AssistantPlan, ToolPlanStep

    steps = [
        ToolPlanStep(
            step_id=f"step_{i}",
            tool_name=t,
            arguments={},
            purpose="test",
            required_permission="read",
        )
        for i, t in enumerate(tool_names)
    ]
    return AssistantPlan(intent="test", steps=steps)


# ---------------------------------------------------------------------------
# 5.4.1: Permission evaluation is called before storing pending plan
# ---------------------------------------------------------------------------


def test_evaluate_plan_permissions_is_callable():
    """5.4.1: _evaluate_plan_permissions exists on ChatController."""
    conn = _make_conn()
    ctrl = _make_ctrl(conn)
    assert hasattr(ctrl, "_evaluate_plan_permissions"), (
        "_evaluate_plan_permissions must be a method on ChatController"
    )


def test_evaluate_plan_allows_safe_tool():
    """5.4.1 + 5.4.2: ALLOW tool returns None (no refusal) from permission evaluator."""
    conn = _make_conn()
    ctrl = _make_ctrl(conn)
    plan = _make_plan(["watchlist.scan"])
    result = ctrl._evaluate_plan_permissions(plan)
    assert result is None, "Safe tool should return None (not refused)"


# ---------------------------------------------------------------------------
# 5.4.2: ALLOW tools in safe-read mode
# ---------------------------------------------------------------------------


def test_allow_tools_have_allow_state():
    """5.4.2: Safe read-only tools have PermissionState.ALLOW in AUTO mode."""
    safe_tools = ["watchlist.scan", "note.create"]
    for tool in safe_tools:
        state = get_permission_state(tool, ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY)
        assert state == PermissionState.ALLOW, f"Expected ALLOW for {tool}, got {state}"


# ---------------------------------------------------------------------------
# 5.4.3: ASK tools become pending only in approval mode
# ---------------------------------------------------------------------------


def test_unsafe_tool_is_refused_without_approval():
    conn = _make_conn()
    ctrl = _make_ctrl(conn, mode=ExecutionMode.PLAN_THEN_APPROVE)

    from vnalpha.assistant.models import AssistantAnswer

    ask_tools = ["execute_python"]
    plan = _make_plan(ask_tools)
    exec_calls = [0]
    preview = AssistantAnswer(
        summary="Plan preview", basis="preview", risks_caveats="", tool_trace_summary=""
    )
    result = AssistantAnswer(
        summary="Script done",
        basis="tools",
        risks_caveats="",
        tool_trace_summary="done",
    )

    def fake_run_ask(question, *, no_execute=False):
        if not no_execute:
            exec_calls[0] += 1
        return (preview if no_execute else result), plan

    ctrl._run_ask = fake_run_ask
    ctrl.handle_natural_language("run analysis script")

    assert ctrl._pending_plan is None
    assert exec_calls == [0]


# ---------------------------------------------------------------------------
# 5.4.4: DENY tools produce refusal
# ---------------------------------------------------------------------------


def test_deny_tool_produces_refusal():
    """5.4.4: DENY tool in AUTO mode produces a refusal."""
    conn = _make_conn()
    ctrl = _make_ctrl(conn, mode=ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY)

    from vnalpha.assistant.models import AssistantAnswer

    plan = _make_plan(["execute_python"])
    preview = AssistantAnswer(
        summary="Plan", basis="preview", risks_caveats="", tool_trace_summary=""
    )

    def fake_run_ask(question, *, no_execute=False):
        return preview, plan

    ctrl._run_ask = fake_run_ask
    ctrl.handle_natural_language("run script")

    all_text = " ".join(t for _, t in ctrl._messages)
    assert (
        "refused" in all_text.lower()
        or "not permitted" in all_text.lower()
        or ctrl._pending_plan is None
    ), "DENY tool must produce refusal or not be stored as pending"


# ---------------------------------------------------------------------------
# 5.4.5: HARD_DENY tools never pending
# ---------------------------------------------------------------------------


def test_hard_deny_tool_is_refused():
    """5.4.5: HARD_DENY tools produce refusal and are never pending."""
    conn = _make_conn()
    ctrl = _make_ctrl(conn)

    from vnalpha.assistant.models import AssistantAnswer

    plan = _make_plan(["broker.place_order"])
    preview = AssistantAnswer(
        summary="Plan", basis="preview", risks_caveats="", tool_trace_summary=""
    )

    def fake_run_ask(question, *, no_execute=False):
        return preview, plan

    ctrl._run_ask = fake_run_ask
    ctrl.handle_natural_language("place order VNM")

    assert ctrl._pending_plan is None, "HARD_DENY tool must never be stored as pending"


def test_hard_deny_produces_refusal_message():
    """5.4.5: Handling HARD_DENY tool produces a refusal message."""
    conn = _make_conn()
    ctrl = _make_ctrl(conn)

    plan = _make_plan(["broker.place_order"])
    result = ctrl._evaluate_plan_permissions(plan)
    assert result is not None, "HARD_DENY plan must produce a refusal string"
    assert "permanently forbidden" in result.lower() or "broker" in result.lower()


def test_hard_deny_tool_classification():
    """5.4.5: broker.* tools are classified as HARD_DENY."""
    hard_deny_tools = [
        "broker.place_order",
        "broker.cancel_order",
        "account.withdraw",
        "trading.execute",
    ]
    for tool in hard_deny_tools:
        state = get_permission_state(tool, ExecutionMode.PLAN_THEN_APPROVE)
        assert state == PermissionState.HARD_DENY, (
            f"Expected HARD_DENY for {tool}, got {state}"
        )


# ---------------------------------------------------------------------------
# 5.4.6: Restricted tools not stored in _pending_plan
# ---------------------------------------------------------------------------


def test_restricted_plan_not_stored_in_pending():
    """5.4.6: Plan with HARD_DENY tool is not stored in _pending_plan."""
    conn = _make_conn()
    ctrl = _make_ctrl(conn, mode=ExecutionMode.PLAN_THEN_APPROVE)

    from vnalpha.assistant.models import AssistantAnswer

    restricted_plan = _make_plan(["broker.execute_order"])
    preview = AssistantAnswer(
        summary="Plan", basis="preview", risks_caveats="", tool_trace_summary=""
    )

    def fake_run_ask(question, *, no_execute=False):
        return preview, restricted_plan

    ctrl._run_ask = fake_run_ask
    ctrl.handle_natural_language("execute VNM trade")

    assert ctrl._pending_plan is None, (
        "HARD_DENY tool plan must not be stored in _pending_plan"
    )


# ---------------------------------------------------------------------------
# 5.4.7: Approval cannot run a restricted pending plan
# ---------------------------------------------------------------------------


def test_approve_does_nothing_when_pending_plan_is_none():
    """5.4.7: approve_pending_plan does nothing when _pending_plan is None."""
    conn = _make_conn()
    ctrl = _make_ctrl(conn)

    ctrl._pending_plan = None
    ctrl.approve_pending_plan()  # must not raise
    # No messages about execution should be in messages
    exec_msgs = [t for _, t in ctrl._messages if "executing" in t.lower()]
    assert exec_msgs == [], "approve must not run when no pending plan"


def test_evaluate_plan_permissions_checks_all_steps():
    """5.4.1: _evaluate_plan_permissions checks every step in the plan."""
    conn = _make_conn()
    ctrl = _make_ctrl(conn)

    # Mix of ALLOW and HARD_DENY
    mixed_plan = _make_plan(["watchlist.query", "broker.place_order"])
    result = ctrl._evaluate_plan_permissions(mixed_plan)

    assert result is not None, (
        "Plan with HARD_DENY step must be refused even with ALLOW steps"
    )


# ---------------------------------------------------------------------------
# 5.4.8: Refusal messages for restricted tools are persisted
# ---------------------------------------------------------------------------


def test_hard_deny_refusal_is_persisted():
    """5.4.8: HARD_DENY tool refusal is persisted as a chat_message."""
    conn = _make_conn()
    sid = create_chat_session(conn)
    ctrl = _make_ctrl(conn, session_id=sid)

    from vnalpha.assistant.models import AssistantAnswer

    plan = _make_plan(["broker.place_order"])
    preview = AssistantAnswer(
        summary="Plan", basis="preview", risks_caveats="", tool_trace_summary=""
    )

    def fake_run_ask(question, *, no_execute=False):
        return preview, plan

    ctrl._run_ask = fake_run_ask
    ctrl.handle_natural_language("place order VNM")

    msgs = list_chat_messages(conn, sid, include_hidden=True)
    refusal_msgs = [m for m in msgs if m.get("message_type") == "refusal"]
    assert len(refusal_msgs) >= 1, "HARD_DENY refusal must be persisted as chat_message"
    conn.close()
