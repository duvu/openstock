"""Tests for CommandRegistry (Tasks 2.1-2.5)."""

from __future__ import annotations

from vnalpha.commands.models import CommandResult, ParsedCommand
from vnalpha.commands.registry import CommandMeta, CommandRegistry


def _dummy_handler(parsed: ParsedCommand, **kwargs) -> CommandResult:
    return CommandResult(status="SUCCESS", title="dummy")


def _make_meta(name: str) -> CommandMeta:
    return CommandMeta(
        name=name,
        description=f"{name} description",
        usage=f"/{name} [args]",
        examples=[f"/{name}"],
        permissions=["READ_WATCHLIST"],
        handler=_dummy_handler,
    )


class TestCommandRegistry:
    def test_register_and_lookup(self):
        reg = CommandRegistry()
        reg.register(_make_meta("scan"))
        meta = reg.get("scan")
        assert meta.name == "scan"
