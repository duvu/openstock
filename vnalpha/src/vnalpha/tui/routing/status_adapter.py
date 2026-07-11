"""RuntimeStatus conversion for the TUI status widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vnalpha.commands.models import CommandResult
    from vnalpha.tui.widgets.status_bar import StatusBar


class TraceEvent(Protocol):
    """The trace fields used by the status projection."""

    status: str
    tool_name: str


class StatusAdapter:
    """Map router activity onto the existing StatusBar API."""

    def __init__(self, status_bar: StatusBar | None) -> None:
        self._status_bar = status_bar

    def routing(self) -> None:
        self.update("ROUTING_INPUT", label="Routing…")

    def command(self, raw: str) -> None:
        self.update("COMMAND_RUNNING", label=raw[:40])

    def chat(self) -> None:
        self.update("CHAT_THINKING", label="Thinking…")

    def ready(self) -> None:
        self.update("READY")

    def error(self, detail: str) -> None:
        self.update("ERROR", detail=detail[:80])

    def warning(self, detail: str) -> None:
        self.update("WARNING", detail=detail[:80])

    def command_result(self, result: CommandResult) -> None:
        from vnalpha.commands.models import CommandStatus

        detail = result.summary or result.title
        match result.status:
            case CommandStatus.SUCCESS | CommandStatus.EMPTY_RESULT:
                if result.warnings:
                    self.warning("; ".join(result.warnings[:2]))
                else:
                    self.update("READY", label=detail[:40])
            case CommandStatus.PARTIAL:
                self.warning(detail)
            case CommandStatus.FAILED | CommandStatus.VALIDATION_ERROR:
                self.error(result.error.message if result.error is not None else detail)

    def trace(self, event: TraceEvent) -> None:
        if event.status == "RUNNING":
            self.update("TOOL_RUNNING", label=event.tool_name)

    def update(self, state_name: str, label: str = "", detail: str = "") -> None:
        if self._status_bar is None:
            return
        try:
            from vnalpha.tui.runtime_status import RuntimeState, RuntimeStatus

            state = RuntimeState(state_name)
            self._status_bar.update_status(
                RuntimeStatus(state=state, label=label, detail=detail)
            )
        except Exception:
            pass
