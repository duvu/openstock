"""Tests for Section 6 — Plan preview and approval (Phase 5.10)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from vnalpha.assistant.models import (
    AssistantPlan,
    AssistantRequest,
    IntentResult,
    PreparedAssistantTurn,
    ToolPlanStep,
)
from vnalpha.chat.modes import (
    ExecutionMode,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(tool_names: list[str]) -> AssistantPlan:
    """Build a minimal AssistantPlan with the given tool names."""
    steps = [
        ToolPlanStep(
            step_id=f"step_{i}",
            tool_name=name,
            arguments={"symbol": "VNM"},
            purpose="test",
            required_permission="read",
        )
        for i, name in enumerate(tool_names)
    ]
    return AssistantPlan(intent="test_intent", steps=steps)


def _make_prepared_turn(plan: AssistantPlan) -> PreparedAssistantTurn:
    return PreparedAssistantTurn(
        prepared_turn_id="prepared-sandbox-turn",
        assistant_session_id="assistant-session",
        request=AssistantRequest(current_user_prompt="run sandbox analysis"),
        intent_result=IntentResult(
            intent="sandbox_research_calculation",
            confidence=1.0,
            entities={},
        ),
        plan=plan,
        plan_hash="sandbox-plan-hash",
        policy_status="PASS",
        created_at="2026-07-12T00:00:00+00:00",
    )


def _make_controller(
    mode: ExecutionMode = ExecutionMode.PLAN_THEN_APPROVE,
) -> tuple[Any, list[tuple[str, str]]]:
    """Return (controller, emitted_messages) for a ChatController with mock deps."""
    messages: list[tuple[str, str]] = []

    def on_message(style: str, text: str) -> None:
        messages.append((style, text))

    # Import here so tests fail loudly if the module is broken
    from vnalpha.chat.controller import ChatController

    schema_connection = MagicMock()
    connection_factory = MagicMock(return_value=schema_connection)
    ctrl = ChatController(
        on_message=on_message,
        connection_factory=connection_factory,
        execution_mode=mode,
    )
    return ctrl, messages


def test_prepare_turn_routes_with_chat_session_identity() -> None:
    controller, _messages = _make_controller()
    controller._chat_session_id = "chat-session"
    app = MagicMock()

    with (
        patch("vnalpha.assistant.app.AssistantApp", return_value=app),
        patch("vnalpha.warehouse.connection.get_connection") as get_connection,
        patch("vnalpha.warehouse.migrations.run_migrations"),
    ):
        get_connection.return_value.close = MagicMock()
        controller._prepare_turn("show candidates", None)

    request = app.prepare.call_args.args[0]
    assert request.routing_session_id == "chat-session"


# ---------------------------------------------------------------------------
# ExecutionMode enum
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# format_plan_preview
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ChatController — PLAN_THEN_APPROVE mode
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ChatController — cancel_pending_plan
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ChatController — approve_pending_plan
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ChatController — AUTO_EXECUTE_SAFE_READ_ONLY mode
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ChatController — PLAN_ONLY mode
# ---------------------------------------------------------------------------
