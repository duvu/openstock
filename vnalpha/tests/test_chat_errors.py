"""Tests for Section 11 — Error and validation handling (tasks 11.1–11.5)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import duckdb
import pytest

from vnalpha.warehouse.migrations import run_migrations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def in_memory_conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


def _make_conn_factory(conn):
    """Return a factory that always returns the same in-memory connection."""

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
# Task 11.5.1–11.5.4: format helpers
# ---------------------------------------------------------------------------


class TestFormatHelpers:
    def test_format_validation_error_contains_warning_and_msg(self):
        from vnalpha.chat.errors import format_validation_error

        result = format_validation_error("bad date")
        assert "WARNING" in result
        assert "bad date" in result

    def test_format_runtime_error_with_detail(self):
        from vnalpha.chat.errors import format_runtime_error

        result = format_runtime_error("db failed", "connection refused")
        assert "ERROR" in result
        assert "db failed" in result
        assert "connection refused" in result

    def test_format_runtime_error_without_detail(self):
        from vnalpha.chat.errors import format_runtime_error

        result = format_runtime_error("db failed")
        assert "ERROR" in result
        assert "db failed" in result

    def test_format_refusal_contains_refused(self):
        from vnalpha.chat.errors import format_refusal

        result = format_refusal("unsafe request")
        assert "REFUSED" in result
        assert "unsafe request" in result

    def test_format_tool_failure_contains_tool_and_error(self):
        from vnalpha.chat.errors import format_tool_failure

        result = format_tool_failure("scan_market", "timeout")
        assert "TOOL FAILED" in result
        assert "scan_market" in result
        assert "timeout" in result


# ---------------------------------------------------------------------------
# Task 11.5.5–11.5.6: error_to_message_type
# ---------------------------------------------------------------------------


class TestErrorToMessageType:
    def test_validation_maps_to_validation_error(self):
        from vnalpha.chat.errors import ChatErrorKind, error_to_message_type

        assert error_to_message_type(ChatErrorKind.VALIDATION) == "validation_error"

    def test_runtime_maps_to_error(self):
        from vnalpha.chat.errors import ChatErrorKind, error_to_message_type

        assert error_to_message_type(ChatErrorKind.RUNTIME) == "error"

    def test_refusal_maps_to_refusal(self):
        from vnalpha.chat.errors import ChatErrorKind, error_to_message_type

        assert error_to_message_type(ChatErrorKind.REFUSAL) == "refusal"

    def test_tool_failed_maps_to_tool_trace_event(self):
        from vnalpha.chat.errors import ChatErrorKind, error_to_message_type

        assert error_to_message_type(ChatErrorKind.TOOL_FAILED) == "tool_trace_event"


# ---------------------------------------------------------------------------
# Task 11.5.7: handle_turn returns error string on RuntimeError
# ---------------------------------------------------------------------------


class TestHandleTurnErrorHandling:
    def test_handle_turn_returns_error_string_not_raises(self, in_memory_conn):
        """handle_turn must return a formatted error string when NL handling raises."""
        from vnalpha.chat.controller import ChatController

        messages = []
        ctrl = ChatController(
            connection_factory=_make_conn_factory(in_memory_conn),
            on_message=lambda s, t: messages.append((s, t)),
            target_date="2026-07-07",
        )

        with patch.object(
            ctrl, "_run_ask", side_effect=RuntimeError("exploded")
        ):
            result = ctrl.handle_turn("show me VN30 stocks")

        assert result is not None
        assert isinstance(result, str)
        assert "ERROR" in result or "exploded" in result

    def test_handle_turn_does_not_raise(self, in_memory_conn):
        """handle_turn swallows exceptions and returns a string."""
        from vnalpha.chat.controller import ChatController

        ctrl = ChatController(
            connection_factory=_make_conn_factory(in_memory_conn),
            on_message=lambda s, t: None,
            target_date="2026-07-07",
        )

        with patch.object(ctrl, "_run_ask", side_effect=ValueError("bad val")):
            try:
                result = ctrl.handle_turn("anything")
            except Exception as exc:
                pytest.fail(f"handle_turn raised unexpectedly: {exc}")

        assert result is not None


# ---------------------------------------------------------------------------
# Task 11.5.8: handle_natural_language handles RefusalMessage
# ---------------------------------------------------------------------------


class TestNaturalLanguageRefusal:
    def test_refusal_message_formatted_and_returned(self, in_memory_conn):
        """handle_natural_language formats RefusalMessage and returns refusal string."""
        from vnalpha.assistant.models import AssistantPlan, RefusalMessage
        from vnalpha.chat.controller import ChatController

        messages = []
        ctrl = ChatController(
            connection_factory=_make_conn_factory(in_memory_conn),
            on_message=lambda s, t: messages.append((s, t)),
            target_date="2026-07-07",
        )

        refusal = RefusalMessage(
            reason="unsafe request",
            policy_category="SAFETY_BYPASS",
        )
        plan = AssistantPlan(intent="scan_candidates", steps=[])

        with patch.object(ctrl, "_run_ask", return_value=(refusal, plan)):
            result = ctrl.handle_natural_language("hack the system")

        # Result should contain the refusal marker
        assert result is not None
        assert "REFUSED" in result
        assert "unsafe request" in result

    def test_refusal_message_posted_via_on_message(self, in_memory_conn):
        """handle_natural_language posts refusal text via on_message."""
        from vnalpha.assistant.models import AssistantPlan, RefusalMessage
        from vnalpha.chat.controller import ChatController

        messages = []
        ctrl = ChatController(
            connection_factory=_make_conn_factory(in_memory_conn),
            on_message=lambda s, t: messages.append((s, t)),
            target_date="2026-07-07",
        )

        refusal = RefusalMessage(
            reason="trading execution not allowed",
            policy_category="TRADING_EXECUTION",
        )
        plan = AssistantPlan(intent="unsupported_or_unsafe", steps=[])

        with patch.object(ctrl, "_run_ask", return_value=(refusal, plan)):
            ctrl.handle_natural_language("buy 100 shares of FPT")

        all_text = " ".join(t for _, t in messages)
        assert "REFUSED" in all_text or "trading execution not allowed" in all_text


# ---------------------------------------------------------------------------
# Task 11.5.9: handle_slash_command returns error string on executor failure
# ---------------------------------------------------------------------------


class TestSlashCommandErrorHandling:
    def test_slash_command_returns_error_string_not_raises(self, in_memory_conn):
        """handle_slash_command returns formatted error string when executor raises."""
        from vnalpha.chat.controller import ChatController

        messages = []
        ctrl = ChatController(
            connection_factory=_make_conn_factory(in_memory_conn),
            on_message=lambda s, t: messages.append((s, t)),
            surface="tui-chat",
            target_date="2026-07-07",
        )

        with patch("vnalpha.chat.controller.CommandExecutor") as MockExec:
            MockExec.return_value.execute.side_effect = RuntimeError("db connection failed")
            result = ctrl.handle_slash_command("/scan --date 2026-07-07")

        assert result is not None
        assert isinstance(result, str)
        assert "ERROR" in result or "db connection failed" in result

    def test_slash_command_does_not_raise_on_exception(self, in_memory_conn):
        """handle_slash_command never raises — always returns or posts error."""
        from vnalpha.chat.controller import ChatController

        ctrl = ChatController(
            connection_factory=_make_conn_factory(in_memory_conn),
            on_message=lambda s, t: None,
            surface="tui-chat",
            target_date="2026-07-07",
        )

        with patch("vnalpha.chat.controller.CommandExecutor") as MockExec:
            MockExec.return_value.execute.side_effect = Exception("unexpected")
            try:
                ctrl.handle_slash_command("/filter")
            except Exception as exc:
                pytest.fail(f"handle_slash_command raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Task 11.3: Persisted messages with session ID
# ---------------------------------------------------------------------------


class TestErrorPersistence:
    def test_refusal_persisted_when_session_id_set(self, in_memory_conn):
        """RefusalMessage is persisted to chat_message table when chat_session_id is set."""
        from vnalpha.assistant.models import AssistantPlan, RefusalMessage
        from vnalpha.chat.controller import ChatController
        from vnalpha.warehouse.chat_repo import (
            create_chat_session,
            list_chat_messages,
        )

        session_id = create_chat_session(in_memory_conn, surface="tui-chat")

        ctrl = ChatController(
            connection_factory=_make_conn_factory(in_memory_conn),
            on_message=lambda s, t: None,
            target_date="2026-07-07",
            chat_session_id=session_id,
        )

        refusal = RefusalMessage(
            reason="cannot execute orders",
            policy_category="TRADING_EXECUTION",
        )
        plan = AssistantPlan(intent="unsupported_or_unsafe", steps=[])

        with patch.object(ctrl, "_run_ask", return_value=(refusal, plan)):
            ctrl.handle_natural_language("buy FPT")

        msgs = list_chat_messages(in_memory_conn, session_id)
        refusal_msgs = [m for m in msgs if m["message_type"] == "refusal"]
        assert len(refusal_msgs) >= 1
        assert "REFUSED" in refusal_msgs[0]["content"]

    def test_runtime_error_persisted_when_session_id_set(self, in_memory_conn):
        """RuntimeError during NL handling is persisted to chat_message with message_type='error'."""
        from vnalpha.chat.controller import ChatController
        from vnalpha.warehouse.chat_repo import (
            create_chat_session,
            list_chat_messages,
        )

        session_id = create_chat_session(in_memory_conn, surface="tui-chat")

        ctrl = ChatController(
            connection_factory=_make_conn_factory(in_memory_conn),
            on_message=lambda s, t: None,
            target_date="2026-07-07",
            chat_session_id=session_id,
        )

        with patch.object(ctrl, "_run_ask", side_effect=RuntimeError("llm timeout")):
            ctrl.handle_natural_language("show VN30")

        msgs = list_chat_messages(in_memory_conn, session_id)
        error_msgs = [m for m in msgs if m["message_type"] == "error"]
        assert len(error_msgs) >= 1
        assert "llm timeout" in error_msgs[0]["content"] or "ERROR" in error_msgs[0]["content"]


# ---------------------------------------------------------------------------
# ChatError dataclass
# ---------------------------------------------------------------------------


class TestChatErrorDataclass:
    def test_chat_error_construction(self):
        from vnalpha.chat.errors import ChatError, ChatErrorKind

        err = ChatError(kind=ChatErrorKind.VALIDATION, message="bad input")
        assert err.kind == ChatErrorKind.VALIDATION
        assert err.message == "bad input"
        assert err.detail is None

    def test_chat_error_with_detail(self):
        from vnalpha.chat.errors import ChatError, ChatErrorKind

        err = ChatError(kind=ChatErrorKind.RUNTIME, message="db error", detail="timeout")
        assert err.detail == "timeout"

    def test_chat_package_exports_error_symbols(self):
        import vnalpha.chat as chat_pkg

        assert hasattr(chat_pkg, "ChatError")
        assert hasattr(chat_pkg, "ChatErrorKind")
        assert hasattr(chat_pkg, "format_validation_error")
        assert hasattr(chat_pkg, "format_runtime_error")
        assert hasattr(chat_pkg, "format_refusal")
        assert hasattr(chat_pkg, "format_tool_failure")
        assert hasattr(chat_pkg, "error_to_message_type")
