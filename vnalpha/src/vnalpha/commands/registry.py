"""Command registry for Phase 5.8 Research Workspace Command Layer."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
        meta = _current_metadata(meta)
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
        """Return command names in deterministic alphabetical order."""
        return sorted(self._commands)

    def execute(
        self,
        parsed: ParsedCommand,
        **handler_kwargs: Any,
    ) -> CommandResult:
        """Dispatch a parsed command to the handler.

        Extra keyword arguments are forwarded to the handler.
        """
        meta = self.get(parsed.command_name)
        return meta.handler(parsed, **handler_kwargs)


def _current_metadata(meta: CommandMeta) -> CommandMeta:
    """Reconcile metadata with enforced command semantics at registration time."""

    if meta.name != "experiment":
        return meta
    return replace(
        meta,
        description="Run indicator experiments or deterministic offline event studies.",
        usage=(
            "/experiment indicator <description> [--universe VN30] "
            "[--start YYYY-MM-DD] [--end YYYY-MM-DD] | "
            "/experiment event-study <ALLOWLISTED_CONDITION> [--horizon N] "
            "[--start YYYY-MM-DD] [--end YYYY-MM-DD]"
        ),
        examples=[
            "/experiment indicator relative strength 20 sessions vs VNINDEX --universe VN30",
            "/experiment event-study rs_20d_vs_vnindex > 0 --horizon 10",
        ],
    )
