from __future__ import annotations

from dataclasses import dataclass, field

from vnalpha.commands.errors import CommandParseError, UnknownCommandError
from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.models import CommandResult, CommandStatus
from vnalpha.commands.parser import parse as parse_command
from vnalpha.commands.registry import CommandAccessMode
from vnalpha.commands.setup import build_default_registry
from vnalpha.warehouse.connection import read_connection
from vnalpha.warehouse.session_repo import (
    create_research_session,
    create_tool_trace,
    finish_research_session,
    finish_tool_trace,
)
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


@dataclass(frozen=True, slots=True)
class CoordinatedCommandExecutor:
    """Execute one command inside the shared warehouse writer lifecycle."""

    surface: str = "cli"
    default_date: str | None = None
    default_date_is_implicit: bool = False
    coordinator: WarehouseWriteCoordinator = field(
        default_factory=WarehouseWriteCoordinator
    )

    def execute(
        self,
        command_text: str,
        *,
        date_override: str | None = None,
        session_scope_id: str | None = None,
    ) -> CommandResult:
        registry = build_default_registry()
        try:
            parsed = parse_command(command_text)
            access_mode = registry.access_mode(parsed)
        except (CommandParseError, UnknownCommandError):
            access_mode = CommandAccessMode.WRITE
        if access_mode is CommandAccessMode.READ:
            with self.coordinator.transaction() as connection:
                session_id = create_research_session(
                    connection,
                    surface=self.surface,
                    command_text=command_text,
                )
                trace_ids = tuple(
                    create_tool_trace(
                        connection,
                        session_id=session_id,
                        trace_parent_type="command",
                        tool_name=tool_name,
                        input_data={"command_name": parsed.command_name},
                    )
                    for tool_name in registry.planned_read_tools(parsed)
                )
            executor: CommandExecutor | None = None
            try:
                with read_connection(path=self.coordinator.path) as connection:
                    executor = CommandExecutor(
                        connection,
                        surface=self.surface,
                        registry=registry,
                        default_date=self.default_date,
                        default_date_is_implicit=self.default_date_is_implicit,
                        deferred_lifecycle=True,
                        session_id=session_id,
                        prestarted_trace_ids=trace_ids,
                    )
                    result = executor.execute(
                        command_text,
                        date_override=date_override,
                        session_scope_id=session_scope_id,
                    )
            except Exception:  # noqa: BROAD_EXCEPT_OK
                with self.coordinator.transaction() as connection:
                    for trace_id in trace_ids:
                        finish_tool_trace(
                            connection,
                            trace_id,
                            status="FAILED",
                            error={
                                "error_type": "RuntimeError",
                                "message": "Command failed. Check logs and retry.",
                            },
                        )
                    finish_research_session(
                        connection,
                        session_id,
                        status=CommandStatus.FAILED,
                        error={
                            "error_type": "RuntimeError",
                            "message": "Command failed. Check logs and retry.",
                        },
                    )
                raise
            with self.coordinator.transaction() as connection:
                executor.persist_deferred_lifecycle(connection, result)
            return result
        with self.coordinator.transaction() as connection:
            return CommandExecutor(
                connection,
                surface=self.surface,
                registry=registry,
                default_date=self.default_date,
                default_date_is_implicit=self.default_date_is_implicit,
            ).execute(
                command_text,
                date_override=date_override,
                session_scope_id=session_scope_id,
            )


__all__ = ["CoordinatedCommandExecutor"]
