"""Shared command execution path for CLI and TUI slash commands."""

from __future__ import annotations

from typing import Any, assert_never

from vnalpha.commands.default_date import accepts_default_date
from vnalpha.commands.errors import (
    CommandError as CommandException,
)
from vnalpha.commands.errors import (
    CommandLifecycleStateError,
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

_GENERIC_COMMAND_FAILURE = "Command failed. Check logs and retry."


class CommandExecutor:
    """Execute one slash command with session and tool-trace persistence."""

    def __init__(
        self,
        conn,
        *,
        surface: str = "cli",
        registry: CommandRegistry | None = None,
        default_date: str | None = None,
        default_date_is_implicit: bool = False,
        deferred_lifecycle: bool = False,
        session_id: str | None = None,
        prestarted_trace_ids: tuple[str, ...] = (),
    ) -> None:
        self._conn = conn
        self._surface = surface
        self._registry = registry or build_default_registry()
        self._default_date = default_date
        self._default_date_is_implicit = default_date_is_implicit
        self._deferred_lifecycle = deferred_lifecycle
        self._session_id = session_id
        self._prestarted_trace_ids = prestarted_trace_ids
        self._parsed_command_name: str | None = None
        self._parsed_arguments: dict[str, Any] | None = None
        self._tool_executor: TracedLocalToolExecutor | None = None

    def execute(
        self,
        command_text: str,
        *,
        date_override: str | None = None,
        session_scope_id: str | None = None,
    ) -> CommandResult:
        """Run a command and persist a research_session regardless of parse outcome."""
        session_id = self._session_id
        if session_id is None:
            if self._deferred_lifecycle:
                raise CommandLifecycleStateError(
                    "Deferred command lifecycle requires a session ID."
                )
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
        elif (
            self._default_date
            and "date" not in parsed.options
            and accepts_default_date(parsed)
        ):
            parsed.options["date"] = (
                "today" if self._default_date_is_implicit else self._default_date
            )

        self._parsed_command_name = parsed.command_name
        self._parsed_arguments = _parsed_args(parsed)
        if not self._deferred_lifecycle:
            update_research_session_parse(
                self._conn,
                session_id,
                parsed.command_name,
                self._parsed_arguments,
            )

        tool_registry = build_local_tool_registry(self._conn)
        tool_executor = TracedLocalToolExecutor(
            self._conn,
            tool_registry,
            session_id=session_id,
            trace_parent_type="command",
            deferred=self._deferred_lifecycle,
            prestarted_trace_ids=self._prestarted_trace_ids,
        )
        self._tool_executor = tool_executor

        try:
            result = self._registry.execute(
                parsed,
                conn=self._conn,
                registry=self._registry,
                surface=self._surface,
                session_id=session_scope_id or session_id,
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
            _capture_exception(exc)
            return self._finish_failed(
                session_id, type(exc).__name__, _GENERIC_COMMAND_FAILURE
            )
        except Exception as exc:
            _capture_exception(exc)
            return self._finish_failed(
                session_id, "RuntimeError", _GENERIC_COMMAND_FAILURE
            )

        if not self._deferred_lifecycle:
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

    def persist_deferred_lifecycle(self, conn, result: CommandResult) -> None:
        if not self._deferred_lifecycle or self._session_id is None:
            raise CommandLifecycleStateError("Command lifecycle is not deferred.")
        if self._parsed_command_name is not None:
            update_research_session_parse(
                conn,
                self._session_id,
                self._parsed_command_name,
                self._parsed_arguments,
            )
        if self._tool_executor is not None:
            self._tool_executor.flush(conn)
        finish_research_session(
            conn,
            self._session_id,
            status=_research_session_status(result.status),
            result_summary={"title": result.title, "summary": result.summary},
            error={
                "error_type": result.error.error_type,
                "message": result.error.message,
            }
            if result.error
            else None,
        )

    def _finish_validation_error(
        self,
        session_id: str,
        error_type: str,
        message: str,
        *,
        title: str,
    ) -> CommandResult:
        if not self._deferred_lifecycle:
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
        if not self._deferred_lifecycle:
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


def _capture_exception(exc: Exception) -> None:
    try:
        from vnalpha.observability.errors import capture_exception

        capture_exception(exc)
    except Exception:  # noqa: BLE001
        pass


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
