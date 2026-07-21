from __future__ import annotations

from dataclasses import dataclass, field

from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.models import CommandResult
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
        with self.coordinator.transaction() as connection:
            return CommandExecutor(
                connection,
                surface=self.surface,
                default_date=self.default_date,
                default_date_is_implicit=self.default_date_is_implicit,
            ).execute(
                command_text,
                date_override=date_override,
                session_scope_id=session_scope_id,
            )


__all__ = ["CoordinatedCommandExecutor"]
