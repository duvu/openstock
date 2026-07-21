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
    def test_answer_projection_removes_credentials_and_terminal_controls(self, conn):
        ctrl, sid = _make_ctrl(conn)
        private_fragment = "CHAT_MESSAGE_SECRET_67"
        hostile = (
            f"password={private_fragment} "
            "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"
        )
        answer = AssistantAnswer(
            summary=hostile,
            basis=hostile,
            risks_caveats=hostile,
            tool_trace_summary=hostile,
        )

        ctrl._emit_assistant_answer(answer)

        stored = _msgs(conn, sid)[0]["content"]
        visible = " ".join(text for _style, text in ctrl._messages)
        assert private_fragment not in stored + visible
        assert "\x1b]8;" not in stored + visible
        assert "[REDACTED]" in stored + visible
