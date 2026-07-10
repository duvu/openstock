"""Shared command execution path for CLI and TUI slash commands."""

from __future__ import annotations

from typing import assert_never

from vnalpha.commands.errors import (
    CommandError as CommandException,
)
from vnalpha.commands.errors import (
    CommandParseError,
    CommandValidationError,
    UnknownCommandError,
)
from vnalpha.commands.models import (
    CommandError,
    CommandResult,
    CommandStatus,
    ParsedCommand,
)
from vnalpha.commands.parser import parse as parse_command
from vnalpha.commands.registry import CommandRegistry
from vnalpha.commands.setup import build_default_registry
from vnalpha.tools.executor import TracedLocalToolExecutor
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.session_repo import (
    create_research_session,
    finish_research_session,
    update_research_session_parse,
)


class CommandExecutor:
    """Execute one slash command with session and tool-trace persistence."""

    def __init__(
        self,
        conn,
        *,
        surface: str = "cli",
        registry: CommandRegistry | None = None,
        default_date: str | None = None,
    ) -> None:
        self._conn = conn
        self._surface = surface
        self._registry = registry or build_default_registry()
        self._default_date = default_date

    def execute(
        self, command_text: str, *, date_override: str | None = None
    ) -> CommandResult:
        """Run a command and persist a research_session regardless of parse outcome."""
        session_id = create_research_session(
            self._conn,
            surface=self._surface,
            command_text=command_text,
        )
        try:
            parsed = parse_command(command_text)
        except CommandParseError as exc:
            return self._finish_validation_error(
                session_id,
                "CommandParseError",
                str(exc),
                title="Command parse error",
            )

        if date_override:
            parsed.options["date"] = date_override
        elif self._default_date and "date" not in parsed.options:
            parsed.options["date"] = self._default_date

        update_research_session_parse(
            self._conn,
            session_id,
            parsed.command_name,
            _parsed_args(parsed),
        )

        tool_registry = build_local_tool_registry(self._conn)
        tool_executor = TracedLocalToolExecutor(
            self._conn,
            tool_registry,
            session_id=session_id,
            trace_parent_type="command",
        )

        try:
            result = self._registry.execute(
                parsed,
                conn=self._conn,
                registry=self._registry,
                session_id=session_id,
                tool_executor=tool_executor,
            )
        except UnknownCommandError as exc:
            return self._finish_validation_error(
                session_id,
                type(exc).__name__,
                str(exc),
                title="Unknown command",
            )
        except CommandValidationError as exc:
            return self._finish_validation_error(
                session_id,
                type(exc).__name__,
                str(exc),
                title="Command validation error",
            )
        except CommandException as exc:
            return self._finish_failed(session_id, type(exc).__name__, str(exc))
        except Exception as exc:
            return self._finish_failed(session_id, "RuntimeError", str(exc))

        finish_research_session(
            self._conn,
            session_id,
            status=_research_session_status(result.status),
            result_summary={"title": result.title, "summary": result.summary},
            error={
                "error_type": result.error.error_type,
                "message": result.error.message,
            }
            if result.error
            else None,
        )
        return result

    def _finish_validation_error(
        self,
        session_id: str,
        error_type: str,
        message: str,
        *,
        title: str,
    ) -> CommandResult:
        finish_research_session(
            self._conn,
            session_id,
            status=CommandStatus.VALIDATION_ERROR,
            error={"error_type": error_type, "message": message},
        )
        return CommandResult(
            status="VALIDATION_ERROR",
            title=title,
            summary=message,
            error=CommandError(error_type=error_type, message=message),
        )

    def _finish_failed(
        self, session_id: str, error_type: str, message: str
    ) -> CommandResult:
        finish_research_session(
            self._conn,
            session_id,
            status=CommandStatus.FAILED,
            error={"error_type": error_type, "message": message},
        )
        return CommandResult(
            status="FAILED",
            title="Command failed",
            summary=message,
            error=CommandError(error_type=error_type, message=message),
        )


def _parsed_args(parsed: ParsedCommand) -> dict:
    return {
        "positional": parsed.positional,
        "filters": [(f.key, f.op, f.value) for f in parsed.filters],
        "options": dict(parsed.options),
    }


def _research_session_status(status: CommandStatus) -> str:
    match status:
        case CommandStatus.SUCCESS:
            return status.value
        case CommandStatus.EMPTY_RESULT:
            return status.value
        case CommandStatus.PARTIAL:
            return status.value
        case CommandStatus.FAILED:
            return status.value
        case CommandStatus.VALIDATION_ERROR:
            return status.value
        case unreachable:
            assert_never(unreachable)
