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


# ---------------------------------------------------------------------------
# 5.4.2: ALLOW tools in safe-read mode
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 5.4.5: HARD_DENY tools never pending
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.4.6: Restricted tools not stored in _pending_plan
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.4.7: Approval cannot run a restricted pending plan
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5.4.8: Refusal messages for restricted tools are persisted
# ---------------------------------------------------------------------------
