"""Tests for TraceEvent and TracedLocalToolExecutor callback infrastructure (task 1.6)."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.tools.executor import TracedLocalToolExecutor, TraceEvent
from vnalpha.tools.models import ToolPermission, ToolSpec
from vnalpha.tools.registry import LocalToolRegistry
from vnalpha.warehouse.migrations import run_migrations

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


@pytest.fixture
def session_id(conn):
    from vnalpha.warehouse.session_repo import create_research_session

    return create_research_session(conn, surface="test", command_text="/test")


def _make_registry_with_mock_tool():
    """Build a LocalToolRegistry with one mock tool 'mock.tool'."""
    from vnalpha.tools.models import ToolOutput

    registry = LocalToolRegistry()
    registry.register(
        ToolSpec(
            name="mock.tool",
            description="Mock tool for testing",
            permission=ToolPermission.READ_WATCHLIST,
        ),
        lambda **kwargs: ToolOutput(
            data=[{"symbol": "FPT"}],
            summary="Mock result",
            warnings=[],
        ),
    )
    return registry


def _make_failing_registry():
    """Build a LocalToolRegistry whose tool always raises."""

    def _fail(**kwargs):
        raise RuntimeError("deliberate failure")

    registry = LocalToolRegistry()
    registry.register(
        ToolSpec(
            name="fail.tool",
            description="Always fails",
            permission=ToolPermission.READ_WATCHLIST,
        ),
        _fail,
    )
    return registry


# ---------------------------------------------------------------------------
# TraceEvent dataclass
# ---------------------------------------------------------------------------


class TestTraceEvent:
    def test_fields_accessible(self):
        evt = TraceEvent(
            tool_name="mock.tool",
            status="RUNNING",
            duration_ms=None,
            tool_trace_id="abc-123",
        )
        assert evt.tool_name == "mock.tool"
        assert evt.status == "RUNNING"
        assert evt.duration_ms is None
        assert evt.tool_trace_id == "abc-123"

    def test_is_dataclass(self):
        import dataclasses

        assert dataclasses.is_dataclass(TraceEvent)


# ---------------------------------------------------------------------------
# TracedLocalToolExecutor callback
# ---------------------------------------------------------------------------


class TestTraceEventCallback:
    def test_callback_called_running_then_success(self, conn, session_id):
        """Callback receives RUNNING then SUCCESS for a successful tool call."""
        events: list[TraceEvent] = []
        registry = _make_registry_with_mock_tool()

        executor = TracedLocalToolExecutor(
            conn,
            registry,
            session_id=session_id,
            trace_parent_type="command",
            trace_event_callback=events.append,
        )
        executor.call("mock.tool", date="2026-07-07")

        assert len(events) == 2
        assert events[0].tool_name == "mock.tool"
        assert events[0].status == "RUNNING"
        assert events[0].duration_ms is None
        assert events[1].status == "SUCCESS"
        assert events[1].tool_name == "mock.tool"
        assert events[1].duration_ms is not None
        assert events[1].duration_ms >= 0

    def test_callback_called_running_then_failed(self, conn, session_id):
        """Callback receives RUNNING then FAILED when tool raises."""
        events: list[TraceEvent] = []
        registry = _make_failing_registry()

        executor = TracedLocalToolExecutor(
            conn,
            registry,
            session_id=session_id,
            trace_parent_type="command",
            trace_event_callback=events.append,
        )
        with pytest.raises(RuntimeError):
            executor.call("fail.tool")

        assert len(events) == 2
        assert events[0].status == "RUNNING"
        assert events[1].status == "FAILED"
        assert events[1].duration_ms is not None

    def test_no_callback_does_not_crash(self, conn, session_id):
        """Executor works fine with no callback (backward compatibility)."""
        registry = _make_registry_with_mock_tool()

        executor = TracedLocalToolExecutor(
            conn,
            registry,
            session_id=session_id,
            trace_parent_type="command",
        )
        output = executor.call("mock.tool", date="2026-07-07")
        assert output is not None

    def test_trace_ids_are_same_in_running_and_success(self, conn, session_id):
        """Both events for the same call share the same tool_trace_id."""
        events: list[TraceEvent] = []
        registry = _make_registry_with_mock_tool()

        executor = TracedLocalToolExecutor(
            conn,
            registry,
            session_id=session_id,
            trace_event_callback=events.append,
        )
        executor.call("mock.tool")

        assert events[0].tool_trace_id == events[1].tool_trace_id
