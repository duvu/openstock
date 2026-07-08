"""Tests for RuntimeStatus model and StatusBar rendering."""

from __future__ import annotations

from vnalpha.tui.runtime_status import RuntimeState, RuntimeStatus


class TestRuntimeState:
    def test_all_states_defined(self):
        expected = {
            "IDLE",
            "ROUTING_INPUT",
            "COMMAND_RUNNING",
            "CHAT_THINKING",
            "TOOL_RUNNING",
            "DATA_ENSURE_RUNNING",
            "DATA_SYNCING",
            "BUILDING_FEATURES",
            "SCORING",
            "READY",
            "WARNING",
            "ERROR",
            "SERVICE_UNAVAILABLE",
        }
        actual = {s.value for s in RuntimeState}
        assert actual == expected


class TestRuntimeStatus:
    def test_default_is_idle(self):
        s = RuntimeStatus()
        assert s.state == RuntimeState.IDLE

    def test_transition_returns_new_status(self):
        s = RuntimeStatus()
        new = s.transition(RuntimeState.COMMAND_RUNNING, label="/explain FPT")
        assert new.state == RuntimeState.COMMAND_RUNNING
        assert new.label == "/explain FPT"
        assert new.started_at is not None

    def test_transition_to_ready_clears_error(self):
        s = RuntimeStatus(state=RuntimeState.ERROR, last_error="oops")
        new = s.transition(RuntimeState.READY)
        assert new.last_error is None

    def test_transition_preserves_error_for_non_ready(self):
        s = RuntimeStatus(state=RuntimeState.ERROR, last_error="oops")
        new = s.transition(RuntimeState.COMMAND_RUNNING)
        assert new.last_error == "oops"

    def test_with_error(self):
        s = RuntimeStatus()
        err = s.with_error("connection failed")
        assert err.state == RuntimeState.ERROR
        assert err.last_error == "connection failed"
        assert err.detail == "connection failed"

    def test_with_warning(self):
        s = RuntimeStatus()
        w = s.with_warning("stale data")
        assert w.state == RuntimeState.WARNING
        assert w.detail == "stale data"

    def test_display_text_ready(self):
        s = RuntimeStatus(state=RuntimeState.READY)
        assert "READY" in s.display_text

    def test_display_text_with_label_and_detail(self):
        s = RuntimeStatus(
            state=RuntimeState.COMMAND_RUNNING,
            label="/explain FPT",
            detail="syncing data",
        )
        text = s.display_text
        assert "RUNNING" in text
        assert "/explain FPT" in text
        assert "syncing data" in text

    def test_display_text_truncates_long_detail(self):
        s = RuntimeStatus(
            state=RuntimeState.ERROR,
            detail="x" * 100,
        )
        text = s.display_text
        assert "…" in text
        assert len(text) < 120


class TestStatusBarFallback:
    """Test the non-Textual fallback StatusBar."""

    def test_fallback_accepts_update(self):
        from vnalpha.tui.widgets.status_bar import StatusBar

        bar = StatusBar()
        bar.update_status(RuntimeStatus(state=RuntimeState.READY))
        assert bar._status.state == RuntimeState.READY
