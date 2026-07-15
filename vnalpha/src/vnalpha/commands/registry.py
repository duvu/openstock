"""Command registry for Phase 5.8 Research Workspace Command Layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from vnalpha.commands.errors import UnknownCommandError
from vnalpha.commands.models import CommandResult, ParsedCommand


@dataclass
class CommandMeta:
    """Metadata for a registered command."""

    name: str
    description: str
    usage: str
    examples: list[str]
    permissions: list[str]
    handler: Callable[..., CommandResult]


class CommandRegistry:
    """Registry of known slash commands.

    Commands must be explicitly registered — unknown names raise UnknownCommandError.
    """

    def __init__(self) -> None:
        self._commands: dict[str, CommandMeta] = {}

    def register(self, meta: CommandMeta) -> None:
        """Register a command. Raises ValueError on duplicate registration."""
        if meta.name in self._commands:
            raise ValueError(
                f"Command '/{meta.name}' is already registered. "
                "Use a unique name or deregister the existing entry first."
            )
        self._commands[meta.name] = meta

    def get(self, name: str) -> CommandMeta:
        """Return the CommandMeta for name, or raise UnknownCommandError."""
        try:
            return self._commands[name]
        except KeyError as exc:
            raise UnknownCommandError(name) from exc

    def all(self) -> list[CommandMeta]:
        """Return all registered commands sorted by name."""
        return sorted(self._commands.values(), key=lambda m: m.name)

    def names(self) -> list[str]:
        """Return discoverable names with ``help`` first, then alphabetical."""
        names = sorted(self._commands.keys())
        if "help" in self._commands:
            names.remove("help")
            names.insert(0, "help")
        return names

    def execute(
        self,
        parsed: ParsedCommand,
        **handler_kwargs: Any,
    ) -> CommandResult:
        """Dispatch a parsed command to its handler.

        Extra keyword arguments are forwarded to the handler.
        """
        meta = self.get(parsed.command_name)
        return meta.handler(parsed, **handler_kwargs)
