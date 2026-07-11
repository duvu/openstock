from __future__ import annotations

from typing import TYPE_CHECKING, Callable, assert_never

from vnalpha.commands.models import CommandStatus
from vnalpha.workspace_context.lifecycle import (
    get_or_create_latest_workspace,
    record_artifact,
    record_input,
)
from vnalpha.workspace_context.models import WorkspaceArtifactRef, WorkspaceState
from vnalpha.workspace_context.persistence import now_iso

if TYPE_CHECKING:
    from vnalpha.commands.models import CommandResult


def load_active_workspace() -> WorkspaceState:
    return get_or_create_latest_workspace()


def record_workspace_input(workspace: WorkspaceState, raw: str) -> None:
    input_kind = "slash_command" if raw.startswith("/") else "natural_language"
    record_input(workspace, raw, input_kind=input_kind)


def record_command_artifacts(workspace: WorkspaceState, result: CommandResult) -> None:
    """Persist artifacts for complete or partial command results only."""

    match result.status:
        case CommandStatus.SUCCESS | CommandStatus.PARTIAL:
            for artifact in result.artifacts:
                created_at = now_iso()
                record_artifact(
                    workspace,
                    WorkspaceArtifactRef(
                        artifact_id=f"command-{created_at}-{artifact.name}",
                        artifact_type="command_result",
                        path="",
                        summary=f"Command artifact: {artifact.name}",
                        created_at=created_at,
                        source_refs=[result.title],
                        metadata={"name": artifact.name},
                    ),
                )
        case (
            CommandStatus.EMPTY_RESULT
            | CommandStatus.FAILED
            | CommandStatus.VALIDATION_ERROR
        ):
            return
        case unreachable:
            assert_never(unreachable)


def refreshed_workspace_for_context_command(
    raw: str,
    status: CommandStatus,
) -> WorkspaceState | None:
    """Reload workspace state after successful context-affecting commands."""

    if status is not CommandStatus.SUCCESS:
        return None
    tokens = raw.split(maxsplit=2)
    match tokens:
        case ["/context", _, *_]:
            return load_active_workspace()
        case ["/todo", "add" | "done" | "block" | "clear-done", *_]:
            return load_active_workspace()
        case [
            "/model",
            "use" | "reset" | "small" | "default" | "reasoning" | "long_context",
            *_,
        ]:
            return load_active_workspace()
        case _:
            return None


def notify_workspace_change(
    callback: Callable[[WorkspaceState], None] | None,
    workspace: WorkspaceState,
) -> None:
    if callback is not None:
        callback(workspace)
