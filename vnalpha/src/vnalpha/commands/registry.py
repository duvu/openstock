"""Command registry for Phase 5.8 Research Workspace Command Layer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Callable

from vnalpha.commands.errors import UnknownCommandError
from vnalpha.commands.models import CommandResult, ParsedCommand


class CommandAccessMode(StrEnum):
    READ = "read"
    WRITE = "write"


_READ_COMMANDS = frozenset(
    {
        "filter",
        "help",
        "history",
        "lineage",
        "market-regime",
        "quality",
        "scan",
        "sector-strength",
        "shortlist",
        "watchlist-summary",
    }
)
_READ_TOOL_PLANS = {
    "filter": ("watchlist.filter",),
    "history": ("history.list_sessions",),
    "lineage": ("lineage.get_symbol_lineage",),
    "quality": ("quality.get_status",),
    "scan": ("watchlist.scan",),
    "shortlist": ("shortlist.generate",),
    "watchlist-summary": ("watchlist.summarize_deep",),
}
_READ_SUBCOMMANDS = {
    "context": frozenset({"export", "list", "status"}),
    "data": frozenset({"gaps"}),
    "feature": frozenset({"validate"}),
    "memory": frozenset({"conflicts", "show", "sources", "status"}),
    "model": frozenset({"explain-route", "profiles", "status"}),
    "repair": frozenset({"status"}),
    "sandbox": frozenset({"artifact", "list", "status"}),
    "scoring-policy": frozenset({"active", "list"}),
    "todo": frozenset({"list"}),
}


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

    def access_mode(self, parsed: ParsedCommand) -> CommandAccessMode:
        self.get(parsed.command_name)
        if parsed.command_name in _READ_COMMANDS:
            return CommandAccessMode.READ
        subcommands = _READ_SUBCOMMANDS.get(parsed.command_name, frozenset())
        if parsed.positional and parsed.positional[0] in subcommands:
            return CommandAccessMode.READ
        return CommandAccessMode.WRITE

    def planned_read_tools(self, parsed: ParsedCommand) -> tuple[str, ...]:
        if self.access_mode(parsed) is not CommandAccessMode.READ:
            return ()
        return _READ_TOOL_PLANS.get(parsed.command_name, ())


def _current_metadata(meta: CommandMeta) -> CommandMeta:
    """Reconcile metadata with enforced command semantics at registration time."""

    if meta.name != "experiment":
        return meta
    return replace(
        meta,
        description="Run indicator experiments, dataset-extension checks, or deterministic offline event studies.",
        usage=(
            "/experiment indicator <description> [--universe VN30] "
            "[--start YYYY-MM-DD] [--end YYYY-MM-DD] | "
            "/experiment event-study <ALLOWLISTED_CONDITION> [--horizon N] "
            "| /experiment dataset-extension <PROVIDER> <DATASET> <EXTENSION> "
            "--consumer <CONSUMER>"
        ),
        examples=[
            "/experiment indicator relative strength 20 sessions vs VNINDEX --universe VN30",
            "/experiment event-study rs_20d_vs_vnindex > 0 --horizon 10",
            "/experiment dataset-extension FNIQUANTX ohlcv openapi --consumer VNALPHA",
        ],
    )
