from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import duckdb
import pytest

from vnalpha.assistant.errors import (
    ActionableToolExecutionError,
    AssistantInputValidationError,
    PlanValidationError,
    ToolExecutionError,
)
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    AssistantRequest,
    IntentResult,
    PreparedAssistantTurn,
    ToolPlanStep,
    plan_hash,
)
from vnalpha.chat.controller import ChatController
from vnalpha.chat.modes import ExecutionMode
from vnalpha.tools.errors import PublicToolFailure
from vnalpha.tools.executor import TraceEvent
from vnalpha.warehouse.chat_repo import create_chat_session, list_chat_messages
from vnalpha.warehouse.migrations import run_migrations

_GENERIC_RETRY = "[ERROR] Assistant request failed. Check logs and retry."


class _NonClosingConnection:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._connection = connection

    def close(self) -> None:
        pass

    def __getattr__(self, name: str):
        return getattr(self._connection, name)


@pytest.fixture
def connection() -> Iterator[duckdb.DuckDBPyConnection]:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    yield conn
    conn.close()


def _prepared_turn() -> PreparedAssistantTurn:
    plan = AssistantPlan(
        intent="fetch_data",
        steps=[
            ToolPlanStep(
                step_id="provision-current-symbol",
                tool_name="data.ensure_current_symbol",
                arguments={"symbol": "FPT"},
                purpose="Provision current-symbol research data.",
                required_permission="WRITE_DATA",
            )
        ],
    )
    return PreparedAssistantTurn(
        prepared_turn_id="turn-issue-230-paths",
        assistant_session_id="assistant-issue-230-paths",
        request=AssistantRequest(current_user_prompt="Phân tích FPT"),
        intent_result=IntentResult(
            intent="fetch_data",
            confidence=1.0,
            entities={"symbol": "FPT"},
        ),
        plan=plan,
        plan_hash=plan_hash(plan),
        policy_status="PASS",
        created_at="2026-07-18T08:33:57+00:00",
    )


def _controller(
    connection: duckdb.DuckDBPyConnection,
    *,
    mode: ExecutionMode = ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS,
) -> tuple[ChatController, str, list[tuple[str, str]]]:
    session_id = create_chat_session(connection)
    messages: list[tuple[str, str]] = []
    controller = ChatController(
        connection_factory=lambda: _NonClosingConnection(connection),
        chat_session_id=session_id,
        execution_mode=mode,
        on_message=lambda style, text: messages.append((style, text)),
    )
    return controller, session_id, messages


def _actionable_failure() -> ToolExecutionError:
    return ActionableToolExecutionError(
        PublicToolFailure(
            reason="FPT readiness failed.",
            remediation=("/data sync FPT", "/build features FPT"),
            correlation_id="correlation-230",
        )
    )


@pytest.mark.parametrize(
    "failure, expected_type, expected_prefix",
    [
        (_actionable_failure(), "tool_failed", "[TOOL FAILED]"),
        (
            AssistantInputValidationError("Invalid date value 'bad'."),
            "validation_error",
            "[WARNING]",
        ),
        (
            PlanValidationError("Plan contains an invalid tool argument."),
            "validation_error",
            "[WARNING]",
        ),
    ],
)
def test_approved_prepared_failures_keep_typed_presentation(
    connection: duckdb.DuckDBPyConnection,
    failure: Exception,
    expected_type: str,
    expected_prefix: str,
) -> None:
    # Given
    controller, session_id, visible_messages = _controller(
        connection, mode=ExecutionMode.PLAN_THEN_APPROVE
    )
    prepared = _prepared_turn()

    # When
    with (
        patch.object(controller, "_prepare_turn", return_value=prepared),
        patch.object(controller, "_execute_prepared_turn", side_effect=failure),
    ):
        controller.handle_natural_language("Phân tích FPT")
        controller.approve_pending_plan()

    # Then
    assert any(text.startswith(expected_prefix) for _, text in visible_messages)
    assert all(_GENERIC_RETRY not in text for _, text in visible_messages)
    transcript = list_chat_messages(connection, session_id)
    typed_rows = [row for row in transcript if row["message_type"] == expected_type]
    assert len(typed_rows) == 1
    assert typed_rows[0]["content"].startswith(expected_prefix)
    assert not [row for row in transcript if row["message_type"] == "error"]


def test_legacy_tool_failure_persists_actionable_message_once(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given
    controller, session_id, visible_messages = _controller(connection)
    prepared = _prepared_turn()
    preview = AssistantAnswer(
        summary="Plan preview",
        basis="preview",
        risks_caveats="",
        tool_trace_summary="not executed",
    )
    calls = 0

    def legacy_run_ask(question, *, no_execute=False, workspace_context=None):
        nonlocal calls
        calls += 1
        if no_execute:
            return preview, prepared.plan
        assert controller._on_trace is not None
        controller._on_trace(
            TraceEvent(
                tool_name="data.ensure_current_symbol",
                status="FAILED",
                duration_ms=1.0,
                tool_trace_id="trace-legacy-230",
            )
        )
        raise _actionable_failure()

    # When
    with patch.object(controller, "_run_ask", side_effect=legacy_run_ask):
        result = controller.handle_natural_language("Phân tích FPT")

    # Then
    assert result is not None
    assert result.startswith("[TOOL FAILED]")
    assert calls == 2
    assert all(_GENERIC_RETRY not in text for _, text in visible_messages)
    transcript = list_chat_messages(connection, session_id)
    tool_failures = [row for row in transcript if row["message_type"] == "tool_failed"]
    assert len(tool_failures) == 1
    assert "FPT readiness failed" in tool_failures[0]["content"]
    assert not [row for row in transcript if row["message_type"] == "error"]


@pytest.mark.parametrize(
    "failure, expected_type, expected_prefix",
    [
        (_actionable_failure(), "tool_failed", "[TOOL FAILED]"),
        (
            AssistantInputValidationError("Invalid date value 'bad'."),
            "validation_error",
            "[WARNING]",
        ),
        (
            PlanValidationError("Plan contains an invalid tool argument."),
            "validation_error",
            "[WARNING]",
        ),
    ],
)
def test_approved_legacy_failures_keep_typed_presentation(
    connection: duckdb.DuckDBPyConnection,
    failure: Exception,
    expected_type: str,
    expected_prefix: str,
) -> None:
    # Given
    controller, session_id, visible_messages = _controller(
        connection, mode=ExecutionMode.PLAN_THEN_APPROVE
    )
    prepared = _prepared_turn()
    preview = AssistantAnswer(
        summary="Plan preview",
        basis="preview",
        risks_caveats="",
        tool_trace_summary="not executed",
    )

    def legacy_run_ask(question, *, no_execute=False, workspace_context=None):
        if no_execute:
            return preview, prepared.plan
        raise failure

    # When
    with patch.object(controller, "_run_ask", side_effect=legacy_run_ask):
        controller.handle_natural_language("Phân tích FPT")
        controller.approve_pending_plan()

    # Then
    assert any(text.startswith(expected_prefix) for _, text in visible_messages)
    assert all(_GENERIC_RETRY not in text for _, text in visible_messages)
    transcript = list_chat_messages(connection, session_id)
    typed_rows = [row for row in transcript if row["message_type"] == expected_type]
    assert len(typed_rows) == 1
    assert typed_rows[0]["content"].startswith(expected_prefix)
    assert not [row for row in transcript if row["message_type"] == "error"]
