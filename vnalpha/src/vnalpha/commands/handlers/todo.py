"""Composer commands for persisted workspace TODO items."""

from __future__ import annotations

from pathlib import Path

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.workspace_context.lifecycle import get_or_create_latest_workspace
from vnalpha.workspace_context.models import WorkspaceState, WorkspaceTask
from vnalpha.workspace_context.tasks import (
    add_task,
    clear_done_tasks,
    update_task_status,
)


def handle_todo(
    parsed: ParsedCommand, *, root: Path | None = None, **_kwargs
) -> CommandResult:
    """Dispatch validated TODO subcommands through immutable workspace mutations."""

    if not parsed.positional:
        raise CommandValidationError(_usage())
    subcommand = parsed.positional[0]
    workspace = get_or_create_latest_workspace(root=root)
    if subcommand == "list":
        _require_argument_count(parsed, 1)
        return _list_result(workspace)
    if subcommand == "add":
        text = " ".join(parsed.positional[1:])
        updated = add_task(workspace, text, root=root)
        task = updated.open_tasks[-1]
        return _item_result("/todo add", "Added TODO item.", task)
    if subcommand == "done":
        task_id = _single_task_id(parsed)
        updated = update_task_status(workspace, task_id, "completed", root=root)
        return _item_result(
            "/todo done", "Completed TODO item.", _task(updated, task_id)
        )
    if subcommand == "block":
        task_id = _single_task_id(parsed)
        updated = update_task_status(workspace, task_id, "blocked", root=root)
        return _item_result(
            "/todo block", "Blocked TODO item.", _task(updated, task_id)
        )
    if subcommand == "clear-done":
        _require_argument_count(parsed, 1)
        before_count = len(workspace.open_tasks)
        updated = clear_done_tasks(workspace, root=root)
        return CommandResult(
            status="SUCCESS",
            title="/todo clear-done",
            summary="Cleared completed TODO items.",
            panels=[
                ResultPanel(
                    title="TODO Update",
                    content={"affected_count": before_count - len(updated.open_tasks)},
                )
            ],
        )
    raise CommandValidationError(
        f"Unsupported /todo subcommand: {subcommand}. {_usage()}"
    )


def _list_result(workspace: WorkspaceState) -> CommandResult:
    rows = [
        {
            "id": task.task_id,
            "status": task.status,
            "priority": task.priority,
            "text": task.text,
            "updated_at": task.updated_at,
        }
        for task in workspace.open_tasks
    ]
    return CommandResult(
        status="SUCCESS",
        title="/todo list",
        summary=f"{len(rows)} TODO item(s).",
        panels=[ResultPanel(title="TODO Items", content={"items": rows})],
    )


def _item_result(title: str, summary: str, task: WorkspaceTask) -> CommandResult:
    return CommandResult(
        status="SUCCESS",
        title=title,
        summary=summary,
        panels=[
            ResultPanel(
                title="TODO Item",
                content={
                    "item_id": task.task_id,
                    "status": task.status,
                    "priority": task.priority,
                    "updated_at": task.updated_at,
                },
            )
        ],
    )


def _single_task_id(parsed: ParsedCommand) -> str:
    _require_argument_count(parsed, 2)
    return parsed.positional[1]


def _task(workspace: WorkspaceState, task_id: str) -> WorkspaceTask:
    for task in workspace.open_tasks:
        if task.task_id == task_id:
            return task
    raise CommandValidationError(f"Unknown TODO item id: {task_id}.")


def _require_argument_count(parsed: ParsedCommand, expected: int) -> None:
    if len(parsed.positional) != expected:
        raise CommandValidationError(_usage())


def _usage() -> str:
    return "Usage: /todo <list|add|done|block|clear-done> [text|id]"
