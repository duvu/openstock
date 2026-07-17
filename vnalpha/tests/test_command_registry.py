"""Tests for CommandRegistry (Tasks 2.1-2.5)."""

from __future__ import annotations

import pytest

from vnalpha.commands.errors import UnknownCommandError
from vnalpha.commands.handlers.help import handle_help
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

    def test_unknown_command_raises(self):
        reg = CommandRegistry()
        with pytest.raises(UnknownCommandError, match="Unknown command: /unknown"):
            reg.get("unknown")

    def test_duplicate_registration_raises(self):
        reg = CommandRegistry()
        reg.register(_make_meta("scan"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_make_meta("scan"))

    def test_names_sorted(self):
        reg = CommandRegistry()
        reg.register(_make_meta("scan"))
        reg.register(_make_meta("explain"))
        reg.register(_make_meta("help"))
        assert reg.names() == ["explain", "help", "scan"]

    def test_all_returns_sorted(self):
        reg = CommandRegistry()
        reg.register(_make_meta("scan"))
        reg.register(_make_meta("explain"))
        names = [m.name for m in reg.all()]
        assert names == ["explain", "scan"]

    def test_execute_dispatches_to_handler(self):
        reg = CommandRegistry()
        reg.register(_make_meta("scan"))
        parsed = ParsedCommand(command_name="scan", raw_text="/scan")
        result = reg.execute(parsed)
        assert result.status == "SUCCESS"

    def test_execute_unknown_raises(self):
        reg = CommandRegistry()
        parsed = ParsedCommand(command_name="unknown", raw_text="/unknown")
        with pytest.raises(UnknownCommandError):
            reg.execute(parsed)


class TestHelpHandler:
    def test_help_returns_table(self):
        reg = CommandRegistry()
        reg.register(_make_meta("scan"))
        reg.register(_make_meta("explain"))
        parsed = ParsedCommand(command_name="help", raw_text="/help")
        result = handle_help(parsed, registry=reg)
        assert result.status == "SUCCESS"
        assert len(result.tables) == 1
        assert result.tables[0].title == "Available Commands"
        # 2 commands
        assert len(result.tables[0].rows) == 2

    def test_tui_help_includes_copy_targets_from_ui_catalog(self):
        reg = CommandRegistry()
        reg.register(_make_meta("help"))
        parsed = ParsedCommand(command_name="help", raw_text="/help")

        result = handle_help(parsed, registry=reg, surface="tui")

        copy_row = next(row for row in result.tables[0].rows if row[0] == "/copy")
        assert copy_row[2] == "/copy result|output|logs|artifact-id"

    def test_help_no_registry(self):
        parsed = ParsedCommand(command_name="help", raw_text="/help")
        result = handle_help(parsed, registry=None)
        assert result.status == "FAILED"

    def test_help_empty_registry(self):
        reg = CommandRegistry()
        parsed = ParsedCommand(command_name="help", raw_text="/help")
        result = handle_help(parsed, registry=reg)
        assert result.status == "SUCCESS"
        assert "No commands" in result.summary
