"""Typed command errors for Phase 5.8 Research Workspace Command Layer."""

from __future__ import annotations


class CommandError(Exception):
    """Base class for all command-layer errors."""


class CommandParseError(CommandError):
    """Raised when a slash command cannot be parsed."""


class UnknownCommandError(CommandError):
    """Raised when a command name is not found in the registry."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown command: /{name}. Run /help for available commands.")


class CommandValidationError(CommandError):
    """Raised when parsed command arguments fail validation."""


class CommandLifecycleStateError(CommandError):
    pass


class ToolPermissionError(CommandError):
    """Raised when a tool is invoked without the required permission."""


class ToolExecutionError(CommandError):
    """Raised when a tool execution fails."""


class RendererError(CommandError):
    """Raised when a command result cannot be rendered."""
