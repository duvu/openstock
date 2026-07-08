"""RuntimeStatus — compact operational state model for the TUI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class RuntimeState(str, Enum):
    """All possible TUI runtime states."""

    IDLE = "IDLE"
    ROUTING_INPUT = "ROUTING_INPUT"
    COMMAND_RUNNING = "COMMAND_RUNNING"
    CHAT_THINKING = "CHAT_THINKING"
    TOOL_RUNNING = "TOOL_RUNNING"
    DATA_ENSURE_RUNNING = "DATA_ENSURE_RUNNING"
    DATA_SYNCING = "DATA_SYNCING"
    BUILDING_FEATURES = "BUILDING_FEATURES"
    SCORING = "SCORING"
    READY = "READY"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


@dataclass
class RuntimeStatus:
    """Current TUI runtime status with label, detail, and timing."""

    state: RuntimeState = RuntimeState.IDLE
    label: str = ""
    detail: str = ""
    started_at: datetime | None = None
    last_error: str | None = None

    def transition(
        self,
        new_state: RuntimeState,
        *,
        label: str = "",
        detail: str = "",
    ) -> "RuntimeStatus":
        """Transition to a new state, recording timing."""
        now = datetime.now(timezone.utc)
        return RuntimeStatus(
            state=new_state,
            label=label,
            detail=detail,
            started_at=now,
            last_error=self.last_error if new_state != RuntimeState.READY else None,
        )

    def with_error(self, error: str) -> "RuntimeStatus":
        """Transition to ERROR state with a message."""
        return RuntimeStatus(
            state=RuntimeState.ERROR,
            label="Error",
            detail=error,
            started_at=datetime.now(timezone.utc),
            last_error=error,
        )

    def with_warning(self, warning: str) -> "RuntimeStatus":
        """Transition to WARNING state with a message."""
        return RuntimeStatus(
            state=RuntimeState.WARNING,
            label="Warning",
            detail=warning,
            started_at=self.started_at,
            last_error=self.last_error,
        )

    @property
    def display_text(self) -> str:
        """Compact one-line display text for the status bar."""
        parts: list[str] = []
        # State badge
        badge = _STATE_BADGES.get(self.state, self.state.value)
        parts.append(badge)
        # Label
        if self.label:
            parts.append(self.label)
        # Detail (truncated)
        if self.detail:
            d = self.detail[:60] + "…" if len(self.detail) > 60 else self.detail
            parts.append(d)
        return " │ ".join(parts)


_STATE_BADGES: dict[RuntimeState, str] = {
    RuntimeState.IDLE: "IDLE",
    RuntimeState.ROUTING_INPUT: "ROUTING",
    RuntimeState.COMMAND_RUNNING: "RUNNING",
    RuntimeState.CHAT_THINKING: "THINKING",
    RuntimeState.TOOL_RUNNING: "TOOL",
    RuntimeState.DATA_ENSURE_RUNNING: "DATA",
    RuntimeState.DATA_SYNCING: "SYNCING",
    RuntimeState.BUILDING_FEATURES: "FEATURES",
    RuntimeState.SCORING: "SCORING",
    RuntimeState.READY: "READY",
    RuntimeState.WARNING: "⚠ WARN",
    RuntimeState.ERROR: "✗ ERROR",
    RuntimeState.SERVICE_UNAVAILABLE: "✗ UNAVAIL",
}
