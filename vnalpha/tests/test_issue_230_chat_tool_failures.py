from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import duckdb
import pytest

from vnalpha.assistant.errors import (
    ActionableToolExecutionError,
    AssistantInputValidationError,
    PlanValidationError,
)
from vnalpha.assistant.models import (
    AssistantPlan,
    AssistantRequest,
    IntentResult,
    PreparedAssistantTurn,
    ToolPlanStep,
    plan_hash,
)
from vnalpha.chat.controller import ChatController
from vnalpha.tools.errors import PublicToolFailure
from vnalpha.warehouse.chat_repo import create_chat_session, list_chat_messages
from vnalpha.warehouse.migrations import run_migrations

_GENERIC_RETRY = "[ERROR] Assistant request failed. Check logs and retry."
_MAX_PUBLIC_ERROR_CHARS = 4_096


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
        prepared_turn_id="turn-issue-230",
        assistant_session_id="assistant-issue-230",
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
) -> tuple[ChatController, str, list[tuple[str, str]]]:
    session_id = create_chat_session(connection)
    messages: list[tuple[str, str]] = []
    controller = ChatController(
        connection_factory=lambda: _NonClosingConnection(connection),
        chat_session_id=session_id,
        on_message=lambda style, text: messages.append((style, text)),
    )
    return controller, session_id, messages


def _run_prepared_failure(
    controller: ChatController,
    error: Exception,
) -> str | None:
    prepared = _prepared_turn()
    with (
        patch.object(controller, "_prepare_turn", return_value=prepared),
        patch.object(
            controller,
            "_execute_prepared_turn",
            side_effect=error,
        ),
    ):
        return controller.handle_natural_language("Phân tích FPT")


def _actionable_failure(
    reason: str,
    remediation: tuple[str, ...] = (),
    correlation_id: str = "correlation-230",
) -> ActionableToolExecutionError:
    return ActionableToolExecutionError(
        PublicToolFailure(
            reason=reason,
            remediation=remediation,
            correlation_id=correlation_id,
        )
    )


def test_typed_tool_failure_preserves_actionable_public_message(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given
    controller, session_id, visible_messages = _controller(connection)
    failure = _actionable_failure(
        "[red]FPT readiness failed[/red]. Authorization: Bearer private-token\x1b[31m",
        remediation=("/data sync FPT", "/build features FPT"),
    )

    # When
    result = _run_prepared_failure(controller, failure)

    # Then
    assert result is not None
    assert result.startswith("[TOOL FAILED]")
    assert "FPT readiness failed" in result
    assert "Remediation: /data sync FPT -> /build features FPT" in result
    assert "correlation_id=correlation-230" in result
    assert "private-token" not in result
    assert "[REDACTED]" in result
    assert "\x1b" not in result
    assert _GENERIC_RETRY not in result
    assert sum(text.startswith("[TOOL FAILED]") for _, text in visible_messages) == 1
    assert all(_GENERIC_RETRY not in text for _, text in visible_messages)

    transcript = list_chat_messages(connection, session_id)
    tool_failures = [row for row in transcript if row["message_type"] == "tool_failed"]
    assert len(tool_failures) == 1
    assert tool_failures[0]["content"] == result


def test_typed_tool_failure_bounds_public_message(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given
    controller, _session_id, _visible_messages = _controller(connection)
    failure = _actionable_failure("x" * (_MAX_PUBLIC_ERROR_CHARS + 1_000))

    # When
    result = _run_prepared_failure(controller, failure)

    # Then
    assert result is not None
    assert result.startswith("[TOOL FAILED] ")
    assert len(result) <= _MAX_PUBLIC_ERROR_CHARS


def test_bounded_tool_failure_retains_actionable_suffix(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given
    controller, _session_id, _visible_messages = _controller(connection)
    failure = _actionable_failure(
        "FPT readiness failed: " + ("x" * (_MAX_PUBLIC_ERROR_CHARS + 1_000)),
        remediation=("/data sync FPT", "/build features FPT"),
    )

    # When
    result = _run_prepared_failure(controller, failure)

    # Then
    assert result is not None
    assert len(result) <= _MAX_PUBLIC_ERROR_CHARS
    assert result.startswith("[TOOL FAILED] FPT readiness failed")
    assert "Remediation: /data sync FPT -> /build features FPT" in result
    assert "correlation_id=correlation-230" in result


@pytest.mark.parametrize(
    "validation_error",
    [
        AssistantInputValidationError("Invalid date value 'bad'."),
        PlanValidationError("Plan contains an invalid tool argument."),
    ],
)
def test_known_validation_uses_validation_presentation(
    connection: duckdb.DuckDBPyConnection,
    validation_error: Exception,
) -> None:
    # Given
    controller, session_id, _visible_messages = _controller(connection)

    # When
    result = _run_prepared_failure(controller, validation_error)

    # Then
    assert result is not None
    assert result.startswith("[WARNING]")
    transcript = list_chat_messages(connection, session_id)
    validation_rows = [
        row for row in transcript if row["message_type"] == "validation_error"
    ]
    assert len(validation_rows) == 1
    assert validation_rows[0]["content"] == result


def test_validation_presentation_bounds_complete_public_message(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    controller, _session_id, _visible_messages = _controller(connection)

    result = _run_prepared_failure(
        controller,
        AssistantInputValidationError("x" * (_MAX_PUBLIC_ERROR_CHARS + 1_000)),
    )

    assert result is not None
    assert result.startswith("[WARNING] ")
    assert len(result) <= _MAX_PUBLIC_ERROR_CHARS


def test_unexpected_failure_keeps_generic_retry_message(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    # Given
    controller, session_id, visible_messages = _controller(connection)

    # When
    result = _run_prepared_failure(
        controller,
        RuntimeError("provider internals and credentials must not leak"),
    )

    # Then
    assert result == _GENERIC_RETRY
    assert all("provider internals" not in text for _, text in visible_messages)
    transcript = list_chat_messages(connection, session_id)
    runtime_rows = [row for row in transcript if row["message_type"] == "error"]
    assert len(runtime_rows) == 1
    assert runtime_rows[0]["content"] == _GENERIC_RETRY
