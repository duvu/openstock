"""Tool-layer errors."""

from __future__ import annotations

from dataclasses import dataclass


class ToolError(Exception):
    """Base class for tool errors."""


class ToolPermissionError(ToolError):
    """Raised when a tool is invoked without required permission."""

    def __init__(self, tool_name: str, required: str) -> None:
        self.tool_name = tool_name
        self.required = required
        super().__init__(f"Tool '{tool_name}' requires permission '{required}'.")


class ToolNotFoundError(ToolError):
    """Raised when a tool name is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool '{name}' is not registered.")


class ToolExecutionError(ToolError):
    """Raised when a tool execution fails."""


@dataclass(frozen=True, slots=True)
class PublicToolFailure:
    """Allowlisted tool-failure fields that may cross a public boundary."""

    reason: str
    remediation: tuple[str, ...]
    correlation_id: str

    def __str__(self) -> str:
        parts = [self.reason.rstrip(".")]
        if self.remediation:
            parts.append("Remediation: " + " -> ".join(self.remediation))
        if self.correlation_id:
            parts.append(f"correlation_id={self.correlation_id}")
        return ". ".join(parts)


class ActionableToolError(ToolExecutionError):
    """Tool-layer failure carrying only explicitly public structured fields."""

    def __init__(self, failure: PublicToolFailure) -> None:
        self.failure = failure
        super().__init__(str(failure))
