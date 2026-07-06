"""/help command handler — lists registered commands from the registry."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultTable,
)


def handle_help(parsed: ParsedCommand, registry=None, **kwargs) -> CommandResult:  # noqa: ANN001
    """Return a table of all registered commands with their descriptions and usage."""
    if registry is None:
        return CommandResult(
            status="FAILED",
            title="/help",
            error=None,
            summary="Registry not available.",
        )

    commands = registry.all()
    if not commands:
        return CommandResult(
            status="SUCCESS",
            title="/help",
            summary="No commands registered.",
        )

    rows = [
        [f"/{meta.name}", meta.description, meta.usage]
        for meta in commands
    ]
    table = ResultTable(
        title="Available Commands",
        columns=[
            ResultColumn(name="command", title="Command"),
            ResultColumn(name="description", title="Description"),
            ResultColumn(name="usage", title="Usage"),
        ],
        rows=rows,
    )
    return CommandResult(
        status="SUCCESS",
        title="/help — Available commands",
        summary=f"{len(commands)} commands registered.",
        tables=[table],
    )
