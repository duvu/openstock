"""RuntimeStatus conversion for the TUI status widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, assert_never

from vnalpha.commands.models import CommandStatus

if TYPE_CHECKING:
    from vnalpha.tui.widgets.status_bar import StatusBar


class TraceEvent(Protocol):
    """The trace fields used by the status projection."""

    status: str
    tool_name: str


class StatusAdapter:
    """Map router activity and command outcomes onto the StatusBar API."""

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

    def command_result(
        self,
        status: CommandStatus,
        summary: str | None,
        warnings: list[str],
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Project command result semantics onto an operator-visible state."""

        detail = _command_detail(summary=summary, warnings=warnings, metadata=metadata)
        match status:
            case CommandStatus.SUCCESS:
                self.warning(detail) if warnings else self.ready()
            case CommandStatus.EMPTY_RESULT:
                self.warning(detail or "No matching result")
            case CommandStatus.PARTIAL:
                self.warning(detail or "Partial result")
            case CommandStatus.FAILED:
                self.error(detail or "Command failed")
            case CommandStatus.VALIDATION_ERROR:
                self.warning(detail or "Invalid command")
            case unreachable:
                assert_never(unreachable)

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


def _command_detail(
    *,
    summary: str | None,
    warnings: list[str],
    metadata: dict[str, object] | None,
) -> str:
    if isinstance(metadata, dict):
        artifact_id = metadata.get("artifact_id")
        if isinstance(artifact_id, str) and artifact_id:
            return artifact_id
    return "; ".join(warnings[:2]) or (summary or "")
