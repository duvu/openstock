"""Tool-layer errors."""

from __future__ import annotations


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
