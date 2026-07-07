"""Tests for Phase 5.10 Sections 2 and 3 — ChatController and unified slash commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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

    expected = {"new", "clear", "context", "plan", "trace", "help"}
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
        assert ctrl.classify_input("Show me strongest VN30 stocks") == "natural_language"

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

    def test_slash_new_is_chat_local(self):
        ctrl = self._make_controller()
        assert ctrl.classify_input("/new") == "chat_local"

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

    with patch(
        "vnalpha.chat.controller.CommandExecutor"
    ) as MockExecutor:
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
    mock_plan = AssistantPlan(intent="scan_candidates", steps=[])

    with patch.object(ctrl, "_run_ask", return_value=(mock_answer, mock_plan)):
        ctrl.handle_natural_language("What are the top VN30 picks today?")

    all_text = " ".join(t for _, t in messages)
    assert "FPT is strong" in all_text


def test_handle_natural_language_posts_error_on_exception():
    """handle_natural_language posts error message when ask() raises."""
    from vnalpha.chat.controller import ChatController

    messages = []
    ctrl = ChatController(
        on_message=lambda s, t: messages.append((s, t)),
        target_date="2026-07-07",
    )

    with patch.object(ctrl, "_run_ask", side_effect=RuntimeError("LLM down")):
        ctrl.handle_natural_language("What is happening?")

    all_text = " ".join(t for _, t in messages)
    assert "LLM down" in all_text or "Error" in all_text


# ---------------------------------------------------------------------------
# Section 2 — Task 2.5: no textual dependency in tests
# ---------------------------------------------------------------------------


def test_chat_controller_no_textual_needed():
    """ChatController and classify_input work without textual installed."""
    # This test itself demonstrates that — it imports only vnalpha.chat.controller
    # which has no textual import anywhere.
    from vnalpha.chat.controller import CHAT_LOCAL_COMMANDS, ChatController

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

    mock_result = CommandResult(
        status="FAILED", title="/scan", summary="No database."
    )

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
