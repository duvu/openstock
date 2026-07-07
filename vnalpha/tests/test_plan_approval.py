"""Tests for Section 6 — Plan preview and approval (Phase 5.10)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    ToolPlanStep,
)
from vnalpha.chat.modes import (
    SAFE_READ_ONLY_TOOLS,
    ExecutionMode,
    format_plan_preview,
    is_safe_read_only_plan,
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


def _make_controller(
    mode: ExecutionMode = ExecutionMode.PLAN_THEN_APPROVE,
) -> tuple[Any, list[tuple[str, str]]]:
    """Return (controller, emitted_messages) for a ChatController with mock deps."""
    messages: list[tuple[str, str]] = []

    def on_message(style: str, text: str) -> None:
        messages.append((style, text))

    # Import here so tests fail loudly if the module is broken
    from vnalpha.chat.controller import ChatController

    ctrl = ChatController(
        on_message=on_message,
        connection_factory=lambda: None,
        execution_mode=mode,
    )
    return ctrl, messages


# ---------------------------------------------------------------------------
# ExecutionMode enum
# ---------------------------------------------------------------------------


class TestExecutionMode:
    def test_has_auto_value(self):
        assert ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY.value == "auto"

    def test_has_plan_then_approve_value(self):
        assert ExecutionMode.PLAN_THEN_APPROVE.value == "plan_then_approve"

    def test_has_plan_only_value(self):
        assert ExecutionMode.PLAN_ONLY.value == "plan_only"

    def test_three_members(self):
        assert len(list(ExecutionMode)) == 3


# ---------------------------------------------------------------------------
# is_safe_read_only_plan
# ---------------------------------------------------------------------------


class TestIsSafeReadOnlyPlan:
    def test_empty_plan_is_safe(self):
        plan = _make_plan([])
        assert is_safe_read_only_plan(plan) is True

    def test_all_safe_tools_returns_true(self):
        plan = _make_plan(["watchlist.scan", "fundamentals.get", "price.get"])
        assert is_safe_read_only_plan(plan) is True

    def test_all_known_safe_tools(self):
        for tool in SAFE_READ_ONLY_TOOLS:
            plan = _make_plan([tool])
            assert is_safe_read_only_plan(plan) is True, f"{tool} should be safe"

    def test_unsafe_tool_returns_false(self):
        plan = _make_plan(["broker.place_order"])
        assert is_safe_read_only_plan(plan) is False

    def test_mixed_safe_and_unsafe_returns_false(self):
        plan = _make_plan(["watchlist.scan", "account.transfer"])
        assert is_safe_read_only_plan(plan) is False

    def test_unknown_tool_returns_false(self):
        plan = _make_plan(["unknown.tool"])
        assert is_safe_read_only_plan(plan) is False


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


# ---------------------------------------------------------------------------
# ChatController — PLAN_THEN_APPROVE mode
# ---------------------------------------------------------------------------


class TestChatControllerPlanThenApprove:
    def _mock_run_ask_plan_only(self, ctrl, plan: AssistantPlan):
        """Patch _run_ask to return (preview_answer, plan) without executing."""
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            return preview_answer, plan

        ctrl._run_ask = fake_run_ask

    def test_handle_natural_language_stores_pending_plan(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        self._mock_run_ask_plan_only(ctrl, plan)

        ctrl.handle_natural_language("show me watchlist")

        assert ctrl._pending_plan is plan

    def test_handle_natural_language_does_not_execute(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        call_count = 0

        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            nonlocal call_count
            call_count += 1
            # Should only ever be called with no_execute=True in PLAN_THEN_APPROVE
            assert no_execute is True, "Should not execute in PLAN_THEN_APPROVE mode"
            return preview_answer, plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("show me watchlist")

        assert call_count == 1  # only the plan call, not the execute call

    def test_handle_natural_language_emits_plan_preview(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        plan = _make_plan(["watchlist.scan"])
        self._mock_run_ask_plan_only(ctrl, plan)

        ctrl.handle_natural_language("show me watchlist")

        # At least one message should contain plan preview text
        all_text = " ".join(t for _, t in messages)
        assert "Plan:" in all_text
        assert "Approve?" in all_text


# ---------------------------------------------------------------------------
# ChatController — cancel_pending_plan
# ---------------------------------------------------------------------------


class TestCancelPendingPlan:
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


# ---------------------------------------------------------------------------
# ChatController — AUTO_EXECUTE_SAFE_READ_ONLY mode
# ---------------------------------------------------------------------------


class TestAutoExecuteSafeReadOnly:
    def test_safe_plan_auto_executes(self):
        ctrl, messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY)
        safe_plan = _make_plan(["watchlist.scan", "price.get"])

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
        ctrl, messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY)
        safe_plan = _make_plan(["price.get"])
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )
        exec_answer = AssistantAnswer(
            summary="Price fetched",
            basis="tools",
            risks_caveats="",
            tool_trace_summary="done",
        )

        def fake_run_ask(question, *, no_execute=False):
            if no_execute:
                return preview_answer, safe_plan
            return exec_answer, safe_plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("get price VNM")

        all_text = " ".join(t for _, t in messages)
        assert "Price fetched" in all_text

    def test_unsafe_plan_stored_as_pending(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_THEN_APPROVE)
        unsafe_plan = _make_plan(["write_file"])
        preview_answer = AssistantAnswer(
            summary="[Plan preview]",
            basis="preview",
            risks_caveats="",
            tool_trace_summary="no exec",
        )

        def fake_run_ask(question, *, no_execute=False):
            assert no_execute is True, "Should preview plan before execution"
            return preview_answer, unsafe_plan

        ctrl._run_ask = fake_run_ask
        ctrl.handle_natural_language("write a file")

        assert ctrl._pending_plan is unsafe_plan

    def test_hard_deny_tool_is_refused_not_pending(self):
        ctrl, messages = _make_controller(ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY)
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

    def test_plan_only_emits_preview(self):
        ctrl, messages = _make_controller(ExecutionMode.PLAN_ONLY)
        plan = _make_plan(["fundamentals.get"])
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
