"""Tests for Section 6 — Plan preview and approval (Phase 5.10)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    AssistantRequest,
    IntentResult,
    PreparedAssistantTurn,
    ToolPlanStep,
)
from vnalpha.assistant.tool_policy import SAFE_TOOLS, is_safe_plan
from vnalpha.chat.modes import (
    ExecutionMode,
    format_plan_preview,
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


class TestExecutionMode:
    def test_has_auto_value(self):
        assert ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS.value == "auto"

    def test_legacy_auto_mode_alias_is_compatible(self):
        assert (
            ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
            is ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS
        )

    def test_has_plan_then_approve_value(self):
        assert ExecutionMode.PLAN_THEN_APPROVE.value == "plan_then_approve"

    def test_has_plan_only_value(self):
        assert ExecutionMode.PLAN_ONLY.value == "plan_only"

    def test_three_members(self):
        assert len(list(ExecutionMode)) == 3


# ---------------------------------------------------------------------------
class TestIsSafePlan:
    def test_empty_plan_is_not_safe(self):
        plan = _make_plan([])
        assert is_safe_plan(plan) is False

    def test_all_safe_tools_returns_true(self):
        plan = _make_plan(["watchlist.scan", "note.create"])
        assert is_safe_plan(plan) is True

    def test_all_known_safe_tools(self):
        for tool in SAFE_TOOLS:
            plan = _make_plan([tool])
            assert is_safe_plan(plan) is True, f"{tool} should be safe"

    def test_unsafe_tool_returns_false(self):
        plan = _make_plan(["broker.place_order"])
        assert is_safe_plan(plan) is False

    def test_mixed_safe_and_unsafe_returns_false(self):
        plan = _make_plan(["watchlist.scan", "account.transfer"])
        assert is_safe_plan(plan) is False

    def test_unknown_tool_returns_false(self):
        plan = _make_plan(["unknown.tool"])
        assert is_safe_plan(plan) is False


# ---------------------------------------------------------------------------
# format_plan_preview
# ---------------------------------------------------------------------------


class TestFormatPlanPreview:
    def test_numbered_steps(self):
        plan = _make_plan(["watchlist.scan", "price.get"])
        result = format_plan_preview(plan)
        assert "1. watchlist.scan" in result
        assert "2. price.get" in result

    def test_contains_approval_prompt(self):
        plan = _make_plan(["price.get"])
        result = format_plan_preview(plan)
        assert "Approve?" in result
        assert "'a' to approve" in result
        assert "Esc to cancel" in result

    def test_starts_with_plan_header(self):
        plan = _make_plan(["price.get"])
        result = format_plan_preview(plan)
        assert result.startswith("Plan:")

    def test_empty_plan(self):
        plan = _make_plan([])
        result = format_plan_preview(plan)
        assert "Plan:" in result
        assert "(no steps)" in result
        assert "Approve?" in result

    def test_args_included_in_output(self):
        steps = [
            ToolPlanStep(
                step_id="s1",
                tool_name="price.get",
                arguments={"symbol": "TCB", "date": "2026-01-01"},
                purpose="test",
                required_permission="read",
            )
        ]
        plan = AssistantPlan(intent="test", steps=steps)
        result = format_plan_preview(plan)
        assert "TCB" in result

    def test_sandbox_preview_includes_materialized_job_metadata(self):
        steps = [
            ToolPlanStep(
                step_id="sandbox-step",
                tool_name="sandbox.run_research_code",
                arguments={
                    "purpose": "compare persisted datasets",
                    "job_id": "job-001",
                    "code_summary": "Writes validated result.json and summary.md.",
                    "code_digest": "a" * 64,
                    "input_references": ["inputs/reference.csv"],
                    "resource_limits": {
                        "cpu_millis": 500,
                        "memory_mb": 256,
                        "timeout_seconds": 30,
                    },
                    "image_digest": f"sha256:{'b' * 64}",
                },
                purpose="test",
                required_permission="SANDBOX_APPROVAL",
            )
        ]
        plan = AssistantPlan(intent="sandbox_research_calculation", steps=steps)

        result = format_plan_preview(plan)

        assert "job-001" in result
        assert "code summary" in result.lower()
        assert "inputs/reference.csv" in result
        assert "500" in result
        assert "256" in result
        assert "30" in result
        assert f"sha256:{'b' * 64}" in result


# ---------------------------------------------------------------------------
# ChatController — PLAN_THEN_APPROVE mode
# ---------------------------------------------------------------------------


class TestChatControllerPlanThenApprove:
    def _mock_run_ask(self, ctrl, plan: AssistantPlan, *, execute_answer: str = "Done"):
        from vnalpha.assistant.models import AssistantAnswer

        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )
        exec_answer = AssistantAnswer(
            summary=execute_answer,
            basis="tools",
            risks_caveats="",
            tool_trace_summary="done",
        )

        def fake_run_ask(question, *, no_execute=False):
            if no_execute:
                return preview_answer, plan
            return exec_answer, plan

        ctrl._run_ask = fake_run_ask

    def test_handle_natural_language_stores_safe_plan_for_approval(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        self._mock_run_ask(ctrl, plan)

        ctrl.handle_natural_language("show me watchlist")

        assert ctrl._pending_plan is plan

    def test_handle_natural_language_does_not_execute_before_approval(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        exec_calls = [0]

        from vnalpha.assistant.models import AssistantAnswer

        preview = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="",
        )
        result = AssistantAnswer(
            summary="Execution result",
            basis="tools",
            risks_caveats="",
            tool_trace_summary="done",
        )

        def fake_run_ask(question, *, no_execute=False):
            if not no_execute:
                exec_calls[0] += 1
            return (preview if no_execute else result), plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("show me watchlist")

        assert exec_calls == [0]

    def test_handle_natural_language_emits_plan_preview(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        self._mock_run_ask(ctrl, plan, execute_answer="Watchlist result")

        ctrl.handle_natural_language("show me watchlist")

        all_text = " ".join(t for _, t in messages)
        assert "Plan:" in all_text

    def test_workspace_context_reaches_planning_and_execution(self):
        ctrl, _messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS)
        plan = _make_plan(["watchlist.scan"])
        calls: list[tuple[str, bool, str | None]] = []
        answer = AssistantAnswer(
            summary="Done",
            basis="test",
            risks_caveats="",
            tool_trace_summary="",
        )

        def fake_run_ask(question, *, no_execute=False, workspace_context=None):
            calls.append((question, no_execute, workspace_context))
            return answer, plan

        ctrl._run_ask = fake_run_ask

        ctrl.handle_natural_language(
            "show me watchlist", workspace_context="# Workspace Context\nstate"
        )

        assert calls == [
            ("show me watchlist", True, "# Workspace Context\nstate"),
            ("show me watchlist", False, "# Workspace Context\nstate"),
        ]

    @pytest.mark.parametrize("no_execute", [True, False])
    def test_run_ask_forwards_workspace_context_to_assistant_app(self, no_execute):
        ctrl, _messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        with patch("vnalpha.warehouse.connection.get_connection"):
            with patch("vnalpha.warehouse.migrations.run_migrations"):
                with patch("vnalpha.assistant.app.AssistantApp") as assistant_app:
                    ctrl._run_ask(
                        "show me watchlist",
                        no_execute=no_execute,
                        workspace_context="# Workspace Context\nstate",
                    )

        assistant_app.return_value.ask.assert_called_once_with(
            "show me watchlist",
            date=None,
            date_is_implicit=False,
            no_execute=no_execute,
            on_trace_event=ctrl._on_trace,
            workspace_context="# Workspace Context\nstate",
        )
        assert ctrl._connection_factory.call_count == 2


class TestPreparedSandboxApproval:
    @pytest.mark.parametrize(
        ("mode", "should_be_pending"),
        [
            (ExecutionMode.PLAN_THEN_APPROVE, True),
            (ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS, True),
            (ExecutionMode.PLAN_ONLY, False),
        ],
    )
    def test_sandbox_plan_previews_without_execution_in_every_mode(
        self, mode: ExecutionMode, should_be_pending: bool
    ) -> None:
        # Given: a prepared turn containing the approval-required sandbox plan
        ctrl, messages = _make_controller(mode)
        plan = _make_plan(["sandbox.run_research_code"])
        prepared = _make_prepared_turn(plan)
        prepared_turns: list[PreparedAssistantTurn] = []
        executed_turns: list[PreparedAssistantTurn] = []

        def fake_prepare_turn(
            question: str, workspace_context: str | None
        ) -> PreparedAssistantTurn:
            prepared_turns.append(prepared)
            return prepared

        def fake_execute_prepared_turn(
            turn: PreparedAssistantTurn,
        ) -> tuple[AssistantAnswer, AssistantPlan]:
            executed_turns.append(turn)
            return (
                AssistantAnswer(
                    summary="Sandbox result",
                    basis="sandbox",
                    risks_caveats="",
                    tool_trace_summary="",
                ),
                plan,
            )

        ctrl._prepare_turn = fake_prepare_turn
        ctrl._execute_prepared_turn = fake_execute_prepared_turn

        # When: the controller handles the natural-language request
        ctrl.handle_natural_language("run sandbox analysis")

        # Then: every mode previews without executing; only approval-capable modes retain it
        assert prepared_turns == [prepared]
        assert executed_turns == []
        assert any("Plan:" in text for _, text in messages)
        if should_be_pending:
            assert ctrl._pending_prepared_turn is prepared
            assert ctrl._pending_plan is plan
        else:
            assert ctrl._pending_prepared_turn is None
            assert ctrl._pending_plan is None

    def test_approval_executes_the_retained_prepared_sandbox_turn(self) -> None:
        # Given: a prepared sandbox turn in approval mode
        ctrl, _messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS)
        plan = _make_plan(["sandbox.run_research_code"])
        prepared = _make_prepared_turn(plan)
        prepared_turns: list[PreparedAssistantTurn] = []
        approved_turns: list[PreparedAssistantTurn] = []
        executed_turns: list[PreparedAssistantTurn] = []

        def fake_prepare_turn(
            question: str, workspace_context: str | None
        ) -> PreparedAssistantTurn:
            prepared_turns.append(prepared)
            return prepared

        def fake_execute_prepared_turn(
            turn: PreparedAssistantTurn,
        ) -> tuple[AssistantAnswer, AssistantPlan]:
            executed_turns.append(turn)
            return (
                AssistantAnswer(
                    summary="Sandbox result",
                    basis="sandbox",
                    risks_caveats="",
                    tool_trace_summary="",
                ),
                plan,
            )

        def fake_approve_prepared_turn(turn: PreparedAssistantTurn) -> None:
            approved_turns.append(turn)

        ctrl._prepare_turn = fake_prepare_turn
        ctrl._approve_prepared_turn = fake_approve_prepared_turn
        ctrl._execute_prepared_turn = fake_execute_prepared_turn

        # When: the user approves the previewed plan
        ctrl.handle_natural_language("run sandbox analysis")
        ctrl.approve_pending_plan()

        # Then: execution receives the identical retained turn without a second prepare
        assert prepared_turns == [prepared]
        assert approved_turns == [prepared]
        assert executed_turns == [prepared]

    def test_approval_rebinds_the_prepared_turn_correlation(self) -> None:
        from vnalpha.observability.context import (
            get_correlation_id,
            set_correlation_id,
        )

        ctrl, _messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS)
        plan = _make_plan(["sandbox.run_research_code"])
        prepared = _make_prepared_turn(plan)
        observed: list[str] = []

        ctrl._prepare_turn = MagicMock(return_value=prepared)
        ctrl._approve_prepared_turn = lambda _turn: observed.append(
            get_correlation_id()
        )
        ctrl._execute_prepared_turn = lambda _turn: (
            observed.append(get_correlation_id())
            or (
                AssistantAnswer(
                    summary="Sandbox result",
                    basis="sandbox",
                    risks_caveats="",
                    tool_trace_summary="",
                ),
                plan,
            )
        )

        set_correlation_id("originating-turn")
        ctrl.handle_natural_language("run sandbox analysis")
        assert ctrl._pending_plan_turn_context == {
            "prepared_turn_id": prepared.prepared_turn_id,
            "correlation_id": "originating-turn",
        }

        set_correlation_id("approval-turn")
        ctrl.approve_pending_plan()

        assert observed == ["originating-turn", "originating-turn"]


# ---------------------------------------------------------------------------
# ChatController — cancel_pending_plan
# ---------------------------------------------------------------------------


class TestCancelPendingPlan:
    def test_prepared_cancel_failure_is_captured_and_not_reported_as_success(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        prepared = _make_prepared_turn(_make_plan(["watchlist.scan"]))
        ctrl._pending_prepared_turn = prepared
        private_fragment = "CANCEL_PRIVATE_63"
        ctrl._connection_factory.side_effect = RuntimeError(
            f"password={private_fragment}"
        )

        with (
            patch.object(ctrl, "_persist_error_message"),
            patch("vnalpha.observability.errors.capture_exception") as capture,
        ):
            ctrl.cancel_pending_plan()

        capture.assert_called_once()
        rendered = " ".join(text for _, text in messages)
        assert "Plan cancellation failed. Check logs and retry." in rendered
        assert "Plan canceled." not in rendered
        assert private_fragment not in rendered
        assert ctrl._pending_prepared_turn is prepared

    def test_cancel_clears_pending_plan(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        ctrl._pending_plan = _make_plan(["watchlist.scan"])
        ctrl._pending_plan_turn_context = {"question": "test"}

        ctrl.cancel_pending_plan()

        assert ctrl._pending_plan is None
        assert ctrl._pending_plan_turn_context is None

    def test_cancel_emits_canceled_message(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        ctrl._pending_plan = _make_plan(["watchlist.scan"])

        ctrl.cancel_pending_plan()

        all_text = " ".join(t for _, t in messages)
        assert "Plan canceled." in all_text

    def test_cancel_noop_when_no_pending_plan(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        assert ctrl._pending_plan is None

        # Should not raise
        ctrl.cancel_pending_plan()

        assert ctrl._pending_plan is None


# ---------------------------------------------------------------------------
# ChatController — approve_pending_plan
# ---------------------------------------------------------------------------


class TestApprovePendingPlan:
    def test_prepared_approval_captures_unexpected_exception(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        prepared = _make_prepared_turn(_make_plan(["watchlist.scan"]))
        ctrl._pending_prepared_turn = prepared
        private_fragment = "PREPARED_APPROVAL_PRIVATE_72"

        with (
            patch.object(ctrl, "_persist_message"),
            patch.object(ctrl, "_persist_error_message"),
            patch.object(
                ctrl,
                "_execute_prepared_turn",
                side_effect=RuntimeError(f"password={private_fragment}"),
            ),
            patch("vnalpha.observability.errors.capture_exception") as capture,
        ):
            ctrl.approve_pending_plan()

        capture.assert_called_once()
        assert private_fragment not in " ".join(text for _, text in messages)

    def test_legacy_approval_captures_unexpected_exception(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        ctrl._pending_plan = _make_plan(["watchlist.scan"])
        ctrl._pending_plan_turn_context = {"question": "show watchlist"}
        private_fragment = "LEGACY_APPROVAL_PRIVATE_81"

        with (
            patch.object(ctrl, "_persist_message"),
            patch.object(ctrl, "_persist_error_message"),
            patch.object(
                ctrl,
                "_run_ask",
                side_effect=RuntimeError(f"password={private_fragment}"),
            ),
            patch("vnalpha.observability.errors.capture_exception") as capture,
        ):
            ctrl.approve_pending_plan()

        capture.assert_called_once()
        assert private_fragment not in " ".join(text for _, text in messages)

    def test_approve_executes_and_clears_plan(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        ctrl._pending_plan = plan
        ctrl._pending_plan_turn_context = {"question": "show me watchlist"}

        executed = []
        good_answer = AssistantAnswer(
            summary="Result from execution",
            basis="tools",
            risks_caveats="",
            tool_trace_summary="done",
        )

        def fake_run_ask(question, *, no_execute=False):
            executed.append(no_execute)
            return good_answer, plan

        ctrl._run_ask = fake_run_ask
        ctrl.approve_pending_plan()

        # Should have called _run_ask with no_execute=False
        assert False in executed
        # Plan should be cleared
        assert ctrl._pending_plan is None
        assert ctrl._pending_plan_turn_context is None

    def test_approve_emits_answer(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        ctrl._pending_plan = plan
        ctrl._pending_plan_turn_context = {"question": "test"}

        good_answer = AssistantAnswer(
            summary="Execution complete",
            basis="tools",
            risks_caveats="",
            tool_trace_summary="done",
        )

        def fake_run_ask(question, *, no_execute=False):
            return good_answer, plan

        ctrl._run_ask = fake_run_ask
        ctrl.approve_pending_plan()

        all_text = " ".join(t for _, t in messages)
        assert "Execution complete" in all_text

    def test_approve_noop_when_no_pending_plan(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        assert ctrl._pending_plan is None

        # Should not raise or call _run_ask
        called = []

        def fake_run_ask(question, *, no_execute=False):
            called.append(True)
            return MagicMock(), _make_plan([])

        ctrl._run_ask = fake_run_ask
        ctrl.approve_pending_plan()

        assert called == []

    def test_approve_preserves_workspace_context_for_execution(self):
        ctrl, _messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        calls: list[tuple[str, bool, str | None]] = []
        answer = AssistantAnswer(
            summary="Done",
            basis="test",
            risks_caveats="",
            tool_trace_summary="",
        )

        def fake_run_ask(question, *, no_execute=False, workspace_context=None):
            calls.append((question, no_execute, workspace_context))
            return answer, plan

        ctrl._run_ask = fake_run_ask
        ctrl._pending_plan = plan
        ctrl._pending_plan_turn_context = {
            "question": "show me watchlist",
            "workspace_context": "# Workspace Context\nstate",
        }

        ctrl.approve_pending_plan()

        assert calls == [("show me watchlist", False, "# Workspace Context\nstate")]

    def test_approve_rebinds_the_legacy_turn_correlation(self):
        from vnalpha.observability.context import (
            get_correlation_id,
            set_correlation_id,
        )

        ctrl, _messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        answer = AssistantAnswer(
            summary="Done",
            basis="test",
            risks_caveats="",
            tool_trace_summary="",
        )
        observed: list[str] = []

        ctrl._pending_plan = plan
        ctrl._pending_plan_turn_context = {
            "question": "show me watchlist",
            "workspace_context": None,
            "correlation_id": "originating-turn",
        }

        def fake_run_ask(question, *, no_execute=False, workspace_context=None):
            observed.append(get_correlation_id())
            return answer, plan

        ctrl._run_ask = fake_run_ask
        set_correlation_id("approval-turn")
        ctrl.approve_pending_plan()

        assert observed == ["originating-turn"]


# ---------------------------------------------------------------------------
# ChatController — AUTO_EXECUTE_SAFE_READ_ONLY mode
# ---------------------------------------------------------------------------


class TestAutoExecuteSafeReadOnly:
    def test_safe_plan_auto_executes(self):
        ctrl, messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS)
        safe_plan = _make_plan(["watchlist.scan", "note.create"])

        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )
        exec_answer = AssistantAnswer(
            summary="Auto-executed result",
            basis="tools",
            risks_caveats="",
            tool_trace_summary="done",
        )
        call_log: list[bool] = []

        def fake_run_ask(question, *, no_execute=False):
            call_log.append(no_execute)
            if no_execute:
                return preview_answer, safe_plan
            return exec_answer, safe_plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("scan watchlist")

        # First call: no_execute=True (planning), second: no_execute=False (execution)
        assert True in call_log
        assert False in call_log
        # Plan should NOT be stored as pending
        assert ctrl._pending_plan is None

    def test_safe_plan_auto_emits_result(self):
        ctrl, messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS)
        safe_plan = _make_plan(["watchlist.scan"])
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )
        exec_answer = AssistantAnswer(
            summary="Watchlist loaded",
            basis="tools",
            risks_caveats="",
            tool_trace_summary="done",
        )

        def fake_run_ask(question, *, no_execute=False):
            if no_execute:
                return preview_answer, safe_plan
            return exec_answer, safe_plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("scan watchlist")

        all_text = " ".join(t for _, t in messages)
        assert "Watchlist loaded" in all_text

    def test_legacy_sandbox_plan_auto_is_refused(self):
        # Given: an approval-required sandbox plan in auto mode
        ctrl, messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS)
        sandbox_plan = _make_plan(["sandbox.run_research_code"])
        call_log: list[bool] = []
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            call_log.append(no_execute)
            return preview_answer, sandbox_plan

        ctrl._run_ask = fake_run_ask

        # When: the controller handles the request
        ctrl.handle_natural_language("run sandbox analysis")

        # Then: it refuses rather than retaining mutable execution context
        assert call_log == [True]
        assert ctrl._pending_plan is None
        assert any("Refused" in text for _, text in messages)

    @pytest.mark.parametrize(
        ("mode", "tool_name"),
        [
            (ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS, "write_file"),
            (ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS, "unknown.tool"),
            (ExecutionMode.PLAN_THEN_APPROVE, "write_file"),
            (ExecutionMode.PLAN_THEN_APPROVE, "unknown.tool"),
        ],
    )
    def test_unsafe_plan_is_refused_without_execution_or_pending(
        self, mode: ExecutionMode, tool_name: str
    ):
        ctrl, messages = _make_controller(mode)
        unsafe_plan = _make_plan([tool_name])
        exec_calls = [0]

        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            if not no_execute:
                exec_calls[0] += 1
            return preview_answer, unsafe_plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("perform an unsafe action")

        assert ctrl._pending_plan is None
        assert exec_calls == [0]
        assert any("Refused" in text for _, text in messages)

    def test_hard_deny_tool_is_refused_not_pending(self):
        ctrl, messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS)
        denied_plan = _make_plan(["broker.place_order"])
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            return preview_answer, denied_plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("place order VNM")

        assert ctrl._pending_plan is None
        all_text = " ".join(t for _, t in messages)
        assert "Refused" in all_text or "refused" in all_text or "forbidden" in all_text


# ---------------------------------------------------------------------------
# ChatController — PLAN_ONLY mode
# ---------------------------------------------------------------------------


class TestPlanOnlyMode:
    def test_plan_only_never_executes(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_ONLY)
        plan = _make_plan(["watchlist.scan"])  # even safe plan should not execute
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )
        exec_called = []

        def fake_run_ask(question, *, no_execute=False):
            if not no_execute:
                exec_called.append(True)
            return preview_answer, plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("anything at all")

        assert exec_called == [], "PLAN_ONLY must never execute"

    def test_plan_only_does_not_store_pending(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_ONLY)
        plan = _make_plan(["watchlist.scan"])
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            return preview_answer, plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("show watchlist")

        # PLAN_ONLY emits preview but does NOT store pending (nothing to approve)
        assert ctrl._pending_plan is None

    def test_legacy_sandbox_plan_only_is_refused(self):
        # Given: an approval-required sandbox plan in plan-only mode
        ctrl, messages = _make_controller(ExecutionMode.PLAN_ONLY)
        sandbox_plan = _make_plan(["sandbox.run_research_code"])
        call_log: list[bool] = []
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            call_log.append(no_execute)
            return preview_answer, sandbox_plan

        ctrl._run_ask = fake_run_ask

        # When: the controller handles the request
        ctrl.handle_natural_language("run sandbox analysis")

        # Then: it refuses rather than previewing mutable execution context
        assert call_log == [True]
        assert ctrl._pending_plan is None
        assert any("Refused" in text for _, text in messages)

    def test_plan_only_emits_preview(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_ONLY)
        plan = _make_plan(["watchlist.scan"])
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            return preview_answer, plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("explain VNM")

        all_text = " ".join(t for _, t in messages)
        assert "Plan:" in all_text
