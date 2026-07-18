"""Tests for Phase 5.10 Sections 2 and 3 — ChatController and unified slash commands."""

from __future__ import annotations

from unittest.mock import patch

import duckdb
import pytest

from vnalpha.warehouse.migrations import run_migrations

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def in_memory_conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


def _make_conn_factory(conn):
    """Return a factory that always returns the same in-memory connection."""

    # We need to NOT close the shared fixture connection, so wrap with a no-op close.
    class _NonClosingConn:
        def __init__(self, inner):
            self._inner = inner

        def close(self):
            pass  # don't close the fixture connection

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def factory():
        return _NonClosingConn(conn)

    return factory


# ---------------------------------------------------------------------------
# Section 2 — Task 2.1: ChatController importable
# ---------------------------------------------------------------------------


def test_chat_controller_importable():
    """ChatController is importable from vnalpha.chat.controller."""
    from vnalpha.chat.controller import ChatController

    assert ChatController is not None


def test_chat_local_commands_constant():
    """CHAT_LOCAL_COMMANDS contains the expected set of local commands."""
    from vnalpha.chat.controller import CHAT_LOCAL_COMMANDS

    expected = {"clear", "context", "plan", "trace", "help"}
    assert CHAT_LOCAL_COMMANDS == expected


# ---------------------------------------------------------------------------
# Section 2 — Task 2.2: Input classification
# ---------------------------------------------------------------------------


class TestClassifyInput:
    def _make_controller(self):
        from vnalpha.chat.controller import ChatController

        return ChatController(
            on_message=lambda style, text: None,
            target_date="2026-07-07",
        )

    def test_natural_language(self):
        ctrl = self._make_controller()
        assert (
            ctrl.classify_input("Show me strongest VN30 stocks") == "natural_language"
        )

    def test_natural_language_empty_prefix(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("what is happening") == "natural_language"

    def test_slash_scan_is_slash_command(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/scan --date 2026-07-07") == "slash_command"

    def test_slash_filter_is_slash_command(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/filter --min-score 0.7") == "slash_command"

    def test_slash_quality_is_slash_command(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/quality") == "slash_command"

    def test_slash_explain_is_slash_command(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/explain FPT") == "slash_command"

    def test_slash_help_is_chat_local(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/help") == "chat_local"

    def test_slash_clear_is_chat_local(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/clear") == "chat_local"

    def test_slash_context_is_chat_local(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/context") == "chat_local"

    def test_slash_plan_is_chat_local(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/plan") == "chat_local"

    def test_slash_trace_is_chat_local(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/trace") == "chat_local"

    def test_unknown_slash_is_slash_command(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/nonexistent") == "slash_command"

    def test_slash_new_is_slash_command(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/new") == "slash_command"

    def test_slash_chat_new_is_slash_command(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/chat new") == "slash_command"


# ---------------------------------------------------------------------------
# Section 2 — Task 2.3: handle_slash_command calls CommandExecutor
# ---------------------------------------------------------------------------


def test_handle_slash_command_calls_executor(in_memory_conn):
    """handle_slash_command instantiates CommandExecutor with surface='tui-chat'."""
    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.models import CommandResult

    messages = []

    def _on_msg(style, text):
        messages.append((style, text))

    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        target_date="2026-07-07",
        surface="tui-chat",
        on_message=_on_msg,
    )

    mock_result = CommandResult(
        status="SUCCESS", title="/scan", summary="3 candidates."
    )

    with patch("vnalpha.chat.controller.CommandExecutor") as MockExecutor:
        instance = MockExecutor.return_value
        instance.execute.return_value = mock_result

        ctrl.handle_slash_command("/scan --date 2026-07-07")

    # Verify CommandExecutor was called with surface='tui-chat'
    MockExecutor.assert_called_once()
    call_kwargs = MockExecutor.call_args.kwargs
    assert call_kwargs.get("surface") == "tui-chat"

    # Verify execute was called with the raw input
    instance.execute.assert_called_once_with("/scan --date 2026-07-07")


def test_handle_slash_command_surface_passed(in_memory_conn):
    """CommandExecutor receives the correct surface tag from ChatController."""
    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.models import CommandResult

    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        target_date="2026-07-07",
        surface="tui-chat",
        on_message=lambda s, t: None,
    )

    mock_result = CommandResult(status="SUCCESS", title="/filter", summary="ok")

    with patch("vnalpha.chat.controller.CommandExecutor") as MockExecutor:
        instance = MockExecutor.return_value
        instance.execute.return_value = mock_result

        ctrl.handle_slash_command("/filter --min-score 0.5")

    call_kwargs = MockExecutor.call_args.kwargs
    assert call_kwargs["surface"] == "tui-chat"


def test_sandbox_slash_command_installs_exact_prepared_turn(in_memory_conn):
    # Given: a successful sandbox command carrying its immutable prepared turn
    from vnalpha.assistant.models import (
        AssistantPlan,
        AssistantRequest,
        IntentResult,
        PreparedAssistantTurn,
        ToolPlanStep,
        plan_hash,
    )
    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.models import CommandResult

    plan = AssistantPlan(
        intent="sandbox_research_calculation",
        steps=[
            ToolPlanStep(
                step_id="sandbox-step",
                tool_name="sandbox.run_research_code",
                arguments={"job_id": "job-command"},
                purpose="numeric research",
                required_permission="SANDBOX_APPROVAL",
            )
        ],
    )
    prepared = PreparedAssistantTurn(
        prepared_turn_id="prepared-command",
        assistant_session_id="assistant-command",
        request=AssistantRequest(current_user_prompt="/sandbox run mean of 1, 2, 3"),
        intent_result=IntentResult(
            intent="sandbox_research_calculation", confidence=1.0, entities={}
        ),
        plan=plan,
        plan_hash=plan_hash(plan),
        policy_status="PASS",
        created_at="2026-07-13T00:00:00+00:00",
    )
    result = CommandResult(
        status="SUCCESS",
        title="/sandbox run",
        summary="awaiting approval",
        pending_prepared_turn=prepared,
    )
    controller = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        surface="tui-chat",
        on_message=lambda _style, _text: None,
    )

    # When: the command is routed through the chat controller
    with patch("vnalpha.chat.controller.CommandExecutor") as executor_type:
        executor_type.return_value.execute.return_value = result
        controller.handle_slash_command("/sandbox run mean of 1, 2, 3")

    # Then: approval retains the exact object rather than reconstructing metadata
    assert controller._pending_prepared_turn is prepared
    assert controller._pending_plan is prepared.plan


# ---------------------------------------------------------------------------
# Section 2 — Task 2.4: handle_natural_language calls AssistantApp.ask
# ---------------------------------------------------------------------------


def test_handle_natural_language_calls_ask():
    """handle_natural_language invokes _run_ask and posts summary via on_message."""
    from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
    from vnalpha.chat.controller import ChatController

    messages = []

    def _on_msg(style, text):
        messages.append((style, text))

    ctrl = ChatController(
        on_message=_on_msg,
        target_date="2026-07-07",
    )

    mock_answer = AssistantAnswer(
        summary="FPT is strong.",
        basis="Watchlist data.",
        risks_caveats="",
        tool_trace_summary="1 tool called.",
    )
    from vnalpha.assistant.models import ToolPlanStep

    mock_plan = AssistantPlan(
        intent="scan_candidates",
        steps=[
            ToolPlanStep(
                step_id="s1",
                tool_name="watchlist.scan",
                arguments={},
                purpose="scan",
                required_permission="READ_DATA",
            )
        ],
    )

    with patch.object(ctrl, "_run_ask", return_value=(mock_answer, mock_plan)):
        ctrl.handle_natural_language("What are the top VN30 picks today?")

    all_text = " ".join(t for _, t in messages)
    assert "FPT is strong" in all_text


def test_handle_natural_language_with_assistant_callback_emits_once():
    """When an assistant callback exists, final answer is routed as one event."""
    from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
    from vnalpha.chat.controller import ChatController

    messages = []
    answers = []

    ctrl = ChatController(
        on_message=lambda s, t: messages.append((s, t)),
        on_assistant_answer=lambda a: answers.append(a),
        target_date="2026-07-07",
    )

    mock_answer = AssistantAnswer(
        summary="FPT is strong.",
        basis="Watchlist data.",
        risks_caveats="",
        tool_trace_summary="1 tool called.",
    )
    from vnalpha.assistant.models import ToolPlanStep

    mock_plan = AssistantPlan(
        intent="scan_candidates",
        steps=[
            ToolPlanStep(
                step_id="s1",
                tool_name="watchlist.scan",
                arguments={},
                purpose="scan",
                required_permission="READ_DATA",
            )
        ],
    )

    with patch.object(ctrl, "_run_ask", return_value=(mock_answer, mock_plan)):
        ctrl.handle_natural_language("What are the top VN30 picks today?")

    assert len(answers) == 1
    assert "FPT is strong" not in " ".join(t for _, t in messages)


def test_handle_natural_language_refusal_emits_once():
    """Refusal responses are not duplicated in on_message output."""
    from vnalpha.assistant.models import AssistantPlan, RefusalMessage
    from vnalpha.chat.controller import ChatController

    messages = []

    ctrl = ChatController(
        on_message=lambda s, t: messages.append((s, t)),
        on_assistant_answer=lambda a: pytest.fail(
            "should not receive structured answer"
        ),
        target_date="2026-07-07",
    )

    mock_plan = AssistantPlan(
        intent="scan_candidates",
        steps=[],
    )
    mock_refusal = RefusalMessage(
        reason="Insufficient context",
        policy_category="UNAVAILABLE_TOOL",
    )

    with patch.object(ctrl, "_run_ask", return_value=(mock_refusal, mock_plan)):
        ctrl.handle_natural_language("What is risk in this stock?")

    refusal_cards = [
        t for _, t in messages if t.startswith("[REFUSED]") or t.startswith("[refused]")
    ]
    assert len(refusal_cards) == 1


def test_handle_natural_language_sanitizes_unexpected_exception():
    from vnalpha.chat.controller import ChatController

    messages = []
    ctrl = ChatController(
        on_message=lambda s, t: messages.append((s, t)),
        target_date="2026-07-07",
    )

    with patch.object(
        ctrl,
        "_run_ask",
        side_effect=RuntimeError("provider internals must not leak"),
    ):
        result = ctrl.handle_natural_language("What is happening?")

    all_text = " ".join(t for _, t in messages)
    assert result == "[ERROR] Assistant request failed. Check logs and retry."
    assert result in all_text
    assert "provider internals must not leak" not in all_text


# ---------------------------------------------------------------------------
# Section 2 — Task 2.5: no textual dependency in tests
# ---------------------------------------------------------------------------


def test_chat_controller_no_textual_needed():
    """ChatController and classify_input work without textual installed."""
    # This test itself demonstrates that — it imports only vnalpha.chat.controller
    # which has no textual import anywhere.
    from vnalpha.chat.controller import ChatController

    ctrl = ChatController(on_message=lambda s, t: None)
    assert ctrl.classify_input("/scan") == "slash_command"
    assert ctrl.classify_input("/help") == "chat_local"
    assert ctrl.classify_input("hello") == "natural_language"


# ---------------------------------------------------------------------------
# Section 3 — Task 3.1–3.6: Slash commands routed via CommandExecutor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_command",
    [
        "/scan --date 2026-07-07",
        "/filter --min-score 0.6",
        "/quality",
        "/explain FPT",
    ],
)
def test_slash_command_routes_to_executor_with_tui_chat_surface(
    raw_command, in_memory_conn
):
    """For /scan, /filter, /quality, /explain: CommandExecutor is called with surface='tui-chat'."""
    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.models import CommandResult

    mock_result = CommandResult(status="SUCCESS", title=raw_command, summary="ok")

    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        target_date="2026-07-07",
        surface="tui-chat",
        on_message=lambda s, t: None,
    )

    with patch("vnalpha.chat.controller.CommandExecutor") as MockExecutor:
        instance = MockExecutor.return_value
        instance.execute.return_value = mock_result
        ctrl.handle_slash_command(raw_command)

    MockExecutor.assert_called_once()
    assert MockExecutor.call_args.kwargs.get("surface") == "tui-chat"
    instance.execute.assert_called_once_with(raw_command)


def test_command_result_success_rendered(in_memory_conn):
    """Successful CommandResult posts green-tagged text via on_message."""
    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.models import CommandResult

    messages = []
    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        target_date="2026-07-07",
        on_message=lambda s, t: messages.append((s, t)),
    )

    mock_result = CommandResult(
        status="SUCCESS", title="/scan", summary="5 results found."
    )

    with patch("vnalpha.chat.controller.CommandExecutor") as MockExecutor:
        instance = MockExecutor.return_value
        instance.execute.return_value = mock_result
        ctrl.handle_slash_command("/scan")

    all_text = " ".join(t for _, t in messages)
    assert "5 results found" in all_text


def test_command_result_failed_rendered(in_memory_conn):
    """FAILED CommandResult posts red-tagged text via on_message."""
    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.models import CommandResult

    messages = []
    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        target_date="2026-07-07",
        on_message=lambda s, t: messages.append((s, t)),
    )

    mock_result = CommandResult(status="FAILED", title="/scan", summary="No database.")

    with patch("vnalpha.chat.controller.CommandExecutor") as MockExecutor:
        instance = MockExecutor.return_value
        instance.execute.return_value = mock_result
        ctrl.handle_slash_command("/scan")

    styles = [s for s, _ in messages]
    assert "red" in styles


def test_command_result_validation_error_rendered(in_memory_conn):
    """VALIDATION_ERROR CommandResult posts yellow-tagged text via on_message."""
    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.models import CommandResult

    messages = []
    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        target_date="2026-07-07",
        on_message=lambda s, t: messages.append((s, t)),
    )

    mock_result = CommandResult(
        status="VALIDATION_ERROR", title="/scan", summary="Missing required field."
    )

    with patch("vnalpha.chat.controller.CommandExecutor") as MockExecutor:
        instance = MockExecutor.return_value
        instance.execute.return_value = mock_result
        ctrl.handle_slash_command("/scan")

    styles = [s for s, _ in messages]
    assert "yellow" in styles


def test_chat_controller_migrations_run_once_for_multiple_persistence_calls(
    in_memory_conn,
):
    from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, RefusalMessage
    from vnalpha.chat.controller import ChatController
    from vnalpha.warehouse.chat_repo import create_chat_session

    sid = create_chat_session(in_memory_conn)
    messages = []
    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        on_message=lambda s, t: messages.append((s, t)),
        on_assistant_answer=lambda a: None,
    )
    ctrl._chat_session_id = sid

    mock_answer = AssistantAnswer(
        summary="ok",
        basis="",
        risks_caveats="",
        tool_trace_summary="",
    )
    mock_plan = AssistantPlan(intent="scan_candidates", steps=[])
    mock_refusal = RefusalMessage(
        reason="not available", policy_category="UNAVAILABLE_TOOL"
    )

    with patch("vnalpha.assistant.app.AssistantApp") as mock_app:
        app_instance = mock_app.return_value
        app_instance.ask.return_value = (mock_answer, mock_plan)
        app_instance.prepare.return_value = (mock_refusal, mock_plan)
        app_instance.execute_prepared.return_value = (mock_answer, mock_plan)

        with patch("vnalpha.warehouse.migrations.run_migrations") as mock_migrations:
            ctrl._persist_message("user", "first", "plain_text")
            ctrl._persist_message("assistant", "second", "plain_text")
            ctrl._run_ask("what is up?")
            ctrl._run_ask("another question")
            assert mock_migrations.call_count == 1


def test_chat_controller_migrations_run_once_for_trace_events(in_memory_conn):
    from types import SimpleNamespace

    from vnalpha.chat.controller import ChatController
    from vnalpha.warehouse.chat_repo import create_chat_session

    sid = create_chat_session(in_memory_conn)
    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        on_message=lambda s, t: None,
        on_assistant_answer=lambda a: None,
    )
    ctrl._chat_session_id = sid

    trace_event = SimpleNamespace(
        tool_name="watchlist.scan",
        status="SUCCESS",
        duration_ms=12.5,
        tool_trace_id="trace-1",
    )

    with patch("vnalpha.warehouse.chat_repo.append_trace_event") as append_trace:
        with patch("vnalpha.warehouse.migrations.run_migrations") as mock_migrations:
            ctrl._on_trace(trace_event)
            ctrl._on_trace(trace_event)
            ctrl._on_trace(trace_event)
            assert mock_migrations.call_count == 1
            assert append_trace.call_count == 3


def test_chat_controller_migrations_run_once_for_failure_paths(in_memory_conn):
    from vnalpha.chat.controller import ChatController
    from vnalpha.chat.errors import ChatErrorKind
    from vnalpha.warehouse.chat_repo import create_chat_session

    sid = create_chat_session(in_memory_conn)
    ctrl = ChatController(
        connection_factory=_make_conn_factory(in_memory_conn),
        on_message=lambda s, t: None,
        on_assistant_answer=lambda a: None,
    )
    ctrl._chat_session_id = sid

    with patch("vnalpha.warehouse.migrations.run_migrations") as mock_migrations:
        ctrl._persist_error_message(
            "temporary assistant failure", ChatErrorKind.RUNTIME
        )
        assert mock_migrations.call_count == 1
