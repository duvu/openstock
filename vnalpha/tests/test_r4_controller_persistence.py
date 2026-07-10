from __future__ import annotations

import duckdb
import pytest

from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep
from vnalpha.chat.controller import ChatController
from vnalpha.chat.modes import ExecutionMode
from vnalpha.warehouse.chat_repo import create_chat_session, list_chat_messages
from vnalpha.warehouse.migrations import run_migrations


def _make_plan(tool_names: list[str]) -> AssistantPlan:
    steps = [
        ToolPlanStep(
            step_id=f"s{i}",
            tool_name=name,
            arguments={},
            purpose="test",
            required_permission="allow",
        )
        for i, name in enumerate(tool_names)
    ]
    return AssistantPlan(intent="test intent", steps=steps)


def _make_answer(summary: str = "Done") -> AssistantAnswer:
    return AssistantAnswer(
        summary=summary, basis="test", risks_caveats="", tool_trace_summary=""
    )


class _NonClosingConn:
    def __init__(self, inner):
        self._inner = inner

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._inner, name)


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


def _make_ctrl(conn, mode=ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY):
    nc = _NonClosingConn(conn)
    session_id = create_chat_session(conn, surface="tui-chat", target_date="2024-01-10")
    messages = []
    ctrl = ChatController(
        connection_factory=lambda: nc,
        on_message=lambda style, text: messages.append((style, text)),
        target_date="2024-01-10",
        execution_mode=mode,
        chat_session_id=session_id,
    )
    ctrl._messages = messages
    return ctrl, session_id


def _msgs(conn, session_id):
    return list_chat_messages(conn, session_id)


def _msg_types(conn, session_id):
    return [m["message_type"] for m in _msgs(conn, session_id)]


def _msg_roles(conn, session_id):
    return [m["role"] for m in _msgs(conn, session_id)]


class TestNaturalLanguagePersistence:
    def test_prompt_persisted_on_natural_language(self, conn):
        ctrl, sid = _make_ctrl(conn)

        def fake_ask(q, *, no_execute=False):
            return _make_answer("Price is 10"), _make_plan(["candidate.explain"])

        ctrl._run_ask = fake_ask
        ctrl.handle_natural_language("get price VNM")

        rows = _msgs(conn, sid)
        assert rows[0]["role"] == "user"
        assert rows[0]["message_type"] == "prompt"
        assert "VNM" in rows[0]["content"]

    def test_plan_preview_persisted_in_plan_only_mode(self, conn):
        ctrl, sid = _make_ctrl(conn, mode=ExecutionMode.PLAN_ONLY)

        def fake_ask(q, *, no_execute=False):
            return _make_answer("Price is 10"), _make_plan(["candidate.explain"])

        ctrl._run_ask = fake_ask
        ctrl.handle_natural_language("analyze VNM")

        types = _msg_types(conn, sid)
        assert "plan_preview" in types

    def test_safe_plan_waits_for_approval_in_plan_then_approve_mode(self, conn):
        ctrl, sid = _make_ctrl(conn, mode=ExecutionMode.PLAN_THEN_APPROVE)
        exec_calls = [0]

        def fake_ask(q, *, no_execute=False):
            if not no_execute:
                exec_calls[0] += 1
            return _make_answer("Done" if not no_execute else "Preview"), _make_plan(
                ["note.create"]
            )

        ctrl._run_ask = fake_ask
        ctrl.handle_natural_language("create a note")

        assert ctrl._pending_plan is not None
        assert exec_calls[0] == 0

    def test_hard_deny_produces_refusal_message(self, conn):
        ctrl, sid = _make_ctrl(conn, mode=ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY)

        def fake_ask(q, *, no_execute=False):
            return _make_answer("Order placed"), _make_plan(["broker.place_order"])

        ctrl._run_ask = fake_ask
        ctrl.handle_natural_language("place order VNM")

        types = _msg_types(conn, sid)
        assert any("refusal" in t or "error" in t for t in types)
        assert ctrl._pending_plan is None


class TestSlashCommandPersistence:
    def _make_fake_result(self, *, status="OK", research_session_id=None):
        class FakeResult:
            pass

        r = FakeResult()
        r.status = status
        r.title = "Scan done"
        r.summary = "Found 3 candidates"
        r.tables = []
        r.metadata = (
            {"research_session_id": research_session_id} if research_session_id else {}
        )
        return r

    def test_slash_command_input_persisted(self, conn):
        ctrl, sid = _make_ctrl(conn)
        fake_result = self._make_fake_result()

        class FakeExecutor:
            def execute(self, raw):
                return fake_result

        import unittest.mock as mock

        with mock.patch(
            "vnalpha.chat.controller.CommandExecutor", return_value=FakeExecutor()
        ):
            ctrl.handle_slash_command("/scan")

        rows = _msgs(conn, sid)
        user_rows = [r for r in rows if r["role"] == "user"]
        assert user_rows[0]["message_type"] == "slash_command"
        assert "/scan" in user_rows[0]["content"]

    def test_slash_command_result_persisted(self, conn):
        ctrl, sid = _make_ctrl(conn)
        fake_result = self._make_fake_result(research_session_id="sess_abc")

        class FakeExecutor:
            def execute(self, raw):
                return fake_result

        import unittest.mock as mock

        with mock.patch(
            "vnalpha.chat.controller.CommandExecutor", return_value=FakeExecutor()
        ):
            ctrl.handle_slash_command("/scan")

        rows = _msgs(conn, sid)
        asst_rows = [r for r in rows if r["role"] == "assistant"]
        assert asst_rows[0]["message_type"] == "slash_command_result"


class TestChatLocalPersistence:
    def test_chat_local_input_persisted(self, conn):
        ctrl, sid = _make_ctrl(conn)
        ctrl.handle_turn("/context")

        rows = _msgs(conn, sid)
        user_rows = [r for r in rows if r["role"] == "user"]
        assert user_rows[0]["message_type"] == "chat_local_command"

    def test_chat_local_result_persisted(self, conn):
        ctrl, sid = _make_ctrl(conn)
        ctrl.handle_turn("/context")

        rows = _msgs(conn, sid)
        sys_rows = [r for r in rows if r["role"] == "system"]
        assert sys_rows[0]["message_type"] == "chat_local_command_result"


class TestPlanApprovalPersistence:
    def test_cancel_persists_plan_cancel(self, conn):
        ctrl, sid = _make_ctrl(conn, mode=ExecutionMode.PLAN_THEN_APPROVE)

        ctrl._pending_plan = _make_plan(["note.create"])
        ctrl._pending_plan_turn_context = {"question": "write report"}

        ctrl.cancel_pending_plan()

        types = _msg_types(conn, sid)
        assert "plan_cancel" in types
        assert ctrl._pending_plan is None

    def test_approve_persists_plan_approval(self, conn):
        ctrl, sid = _make_ctrl(conn, mode=ExecutionMode.PLAN_THEN_APPROVE)
        call_count = [0]

        def fake_ask(q, *, no_execute=False):
            call_count[0] += 1
            return _make_answer("Done"), _make_plan(["note.create"])

        ctrl._run_ask = fake_ask
        ctrl._pending_plan = _make_plan(["note.create"])
        ctrl._pending_plan_turn_context = {"question": "write report"}
        ctrl.approve_pending_plan()

        types = _msg_types(conn, sid)
        assert "plan_approval" in types
        assert call_count[0] >= 1


class TestNoPersistWithoutSession:
    def test_no_crash_when_session_id_is_none(self):
        messages = []
        ctrl = ChatController(
            connection_factory=lambda: duckdb.connect(":memory:"),
            on_message=lambda style, text: messages.append((style, text)),
            target_date="2024-01-10",
            execution_mode=ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY,
            chat_session_id=None,
        )
        ctrl._persist_message("user", "hello", "prompt")
