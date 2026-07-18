from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import patch

import duckdb
import pytest

from vnalpha.assistant.errors import (
    ActionableToolExecutionError,
    ToolExecutionError,
)
from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import (
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
from vnalpha.tools.models import ToolOutput, ToolPermission, ToolSpec
from vnalpha.tools.registry import LocalToolRegistry
from vnalpha.warehouse.assistant_repo import create_assistant_session
from vnalpha.warehouse.chat_repo import create_chat_session, list_chat_messages
from vnalpha.warehouse.migrations import run_migrations

_GENERIC_RETRY = "[ERROR] Assistant request failed. Check logs and retry."
_PRIVATE_DSN = "postgresql://alice:s3cr3t@db.internal/research"


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
        prepared_turn_id="turn-issue-230-surfaces",
        assistant_session_id="assistant-issue-230-surfaces",
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


def test_actionable_tool_failure_has_structured_public_contract() -> None:
    # Given
    failure = PublicToolFailure(
        reason="FPT readiness failed.",
        remediation=("/data sync FPT", "/build features FPT"),
        correlation_id="correlation-230",
    )

    # When / Then
    error = ActionableToolExecutionError(failure)
    assert error.failure == failure
    assert "Remediation: /data sync FPT -> /build features FPT" in str(error)
    assert "correlation_id=correlation-230" in str(error)


def test_unclassified_assistant_tool_error_uses_generic_retry(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given
    controller, session_id, visible_messages = _controller(connection)
    prepared = _prepared_turn()

    # When
    with (
        patch.object(controller, "_prepare_turn", return_value=prepared),
        patch.object(
            controller,
            "_execute_prepared_turn",
            side_effect=ToolExecutionError(f"unexpected {_PRIVATE_DSN}"),
        ),
    ):
        result = controller.handle_natural_language("Phân tích FPT")

    # Then
    assert result == _GENERIC_RETRY
    assert all(_PRIVATE_DSN not in text for _, text in visible_messages)
    transcript = list_chat_messages(connection, session_id)
    assert [row["message_type"] for row in transcript] == ["prompt", "error"]
    assert _PRIVATE_DSN not in transcript[-1]["content"]


def test_unexpected_tool_runtime_error_stays_generic_through_real_executor(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given
    from vnalpha.assistant.app import AssistantApp as RealAssistantApp

    controller, session_id, visible_messages = _controller(connection)
    assistant_session_id = create_assistant_session(
        connection, surface="test", user_prompt="analyze FPT"
    )
    prepared = replace(_prepared_turn(), assistant_session_id=assistant_session_id)
    registry = LocalToolRegistry()

    def fail_unexpectedly(**_kwargs) -> ToolOutput:
        raise RuntimeError(f"provider internals at {_PRIVATE_DSN}")

    registry.register(
        ToolSpec(
            name="data.ensure_current_symbol",
            description="Fail unexpectedly for boundary verification.",
            permission=ToolPermission.WRITE_DATA,
        ),
        fail_unexpectedly,
    )

    def app_factory(conn, *, surface="cli"):
        return RealAssistantApp(conn, surface=surface, llm_client=FakeLLMClient())

    # When
    with (
        patch.object(controller, "_prepare_turn", return_value=prepared),
        patch("vnalpha.assistant.app.AssistantApp", app_factory),
        patch(
            "vnalpha.assistant.executor._build_tool_registry",
            return_value=registry,
        ),
    ):
        result = controller.handle_natural_language("Phân tích FPT")

    # Then
    assert result == _GENERIC_RETRY
    assert all(_PRIVATE_DSN not in text for _, text in visible_messages)
    transcript = list_chat_messages(connection, session_id)
    assert [row["message_type"] for row in transcript] == ["prompt", "error"]
    assert _PRIVATE_DSN not in transcript[-1]["content"]
    tool_rows = connection.execute(
        "SELECT tool_name, status, error_json FROM tool_trace ORDER BY started_at"
    ).fetchall()
    assert [(row[0], row[1]) for row in tool_rows] == [
        ("data.ensure_current_symbol", "FAILED")
    ]
    assert _PRIVATE_DSN not in tool_rows[0][2]
    session_error = connection.execute(
        "SELECT error_json FROM assistant_session WHERE assistant_session_id = ?",
        [assistant_session_id],
    ).fetchone()[0]
    assert _PRIVATE_DSN not in session_error


def test_unexpected_tool_runtime_error_preserves_assistant_error_contract(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given
    registry = LocalToolRegistry()

    def fail_unexpectedly(**_kwargs) -> ToolOutput:
        raise RuntimeError("provider implementation failed")

    registry.register(
        ToolSpec(
            name="data.ensure_current_symbol",
            description="Fail unexpectedly for boundary verification.",
            permission=ToolPermission.WRITE_DATA,
        ),
        fail_unexpectedly,
    )
    assistant_session_id = create_assistant_session(
        connection, surface="test", user_prompt="analyze FPT"
    )
    # When / Then
    with patch(
        "vnalpha.assistant.executor._build_tool_registry", return_value=registry
    ):
        executor = AssistantExecutor(
            connection, assistant_session_id=assistant_session_id
        )
        with pytest.raises(ToolExecutionError, match="provider implementation failed"):
            executor.execute(_prepared_turn().plan)
