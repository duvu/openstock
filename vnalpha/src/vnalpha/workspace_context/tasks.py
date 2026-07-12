"""Immutable persisted workspace task mutations for composer commands."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from vnalpha.commands.errors import CommandValidationError
from vnalpha.workspace_context.models import WorkspaceState, WorkspaceTask
from vnalpha.workspace_context.observability import emit_workspace_audit_event
from vnalpha.workspace_context.persistence import (
    now_iso,
    persist_workspace_unlocked,
    workspace_mutation,
)
from vnalpha.workspace_context.redaction import redact_workspace_text
from vnalpha.workspace_context.retention import enforce_retention
from vnalpha.workspace_context.storage import append_workspace_event


def add_task(
    workspace: WorkspaceState, text: str, *, root: Path | None = None
) -> WorkspaceState:
    """Persist one pending, medium-priority task and emit redacted metadata."""

    task_text = redact_workspace_text(text.strip()).text
    if not task_text:
        raise CommandValidationError("Usage: /todo add <text>.")
    with workspace_mutation(workspace.workspace_id, root=root) as (
        resolved_root,
        current,
    ):
        now = now_iso()
        task = WorkspaceTask(
            task_id=f"task-{uuid4().hex[:8]}",
            text=task_text,
            status="pending",
            priority="medium",
            created_at=now,
            updated_at=now,
            source_refs=["composer_command"],
        )
        updated = _with_tasks(current, [*current.open_tasks, task], now)
        updated = _persist_item_event(
            updated,
            event_type="TUI_TODO_ITEM_ADDED",
            summary="TODO item added",
            metadata=_item_metadata(task),
            root=resolved_root,
        )
        return updated


def update_task_status(
    workspace: WorkspaceState,
    task_id: str,
    status: str,
    *,
    root: Path | None = None,
) -> WorkspaceState:
    """Persist a new status for an existing task and emit redacted metadata."""

    with workspace_mutation(workspace.workspace_id, root=root) as (
        resolved_root,
        current,
    ):
        now = now_iso()
        updated_task: WorkspaceTask | None = None
        updated_tasks: list[WorkspaceTask] = []
        for task in current.open_tasks:
            if task.task_id == task_id:
                updated_task = WorkspaceTask(
                    task_id=task.task_id,
                    text=task.text,
                    status=status,
                    priority=task.priority,
                    created_at=task.created_at,
                    updated_at=now,
                    source_refs=list(task.source_refs),
                )
                updated_tasks.append(updated_task)
            else:
                updated_tasks.append(task)
        if updated_task is None:
            raise CommandValidationError(f"Unknown TODO item id: {task_id}.")
        updated = _with_tasks(current, updated_tasks, now)
        updated = _persist_item_event(
            updated,
            event_type="TUI_TODO_ITEM_UPDATED",
            summary="TODO item updated",
            metadata=_item_metadata(updated_task),
            root=resolved_root,
        )
        return updated


def clear_done_tasks(
    workspace: WorkspaceState, *, root: Path | None = None
) -> WorkspaceState:
    """Remove completed legacy and current task statuses from persisted state."""

    with workspace_mutation(workspace.workspace_id, root=root) as (
        resolved_root,
        current,
    ):
        remaining = [
            task
            for task in current.open_tasks
            if task.status not in {"completed", "done"}
        ]
        affected_count = len(current.open_tasks) - len(remaining)
        now = now_iso()
        updated = _with_tasks(current, remaining, now)
        metadata = {
            "affected_count": affected_count,
            "redaction_status": "redacted",
            "source": "composer_command",
        }
        updated = _persist_item_event(
            updated,
            event_type="TUI_TODO_ITEM_UPDATED",
            summary="Completed TODO items cleared",
            metadata=metadata,
            root=resolved_root,
        )
        return updated


def _with_tasks(
    state: WorkspaceState, tasks: list[WorkspaceTask], updated_at: str
) -> WorkspaceState:
    return WorkspaceState.from_dict(
        {
            **state.to_dict(),
            "open_tasks": [task.to_dict() for task in tasks],
            "updated_at": updated_at,
            "context_size": {
                **state.context_size,
                "events": state.context_size.get("events", 0) + 1,
            },
        }
    )


def _item_metadata(task: WorkspaceTask) -> dict[str, str | int]:
    return {
        "item_id": task.task_id,
        "priority": task.priority,
        "redaction_status": "redacted",
        "source": "composer_command",
        "status": task.status,
        "title_length": len(task.text),
    }


def _persist_item_event(
    state: WorkspaceState,
    *,
    event_type: str,
    summary: str,
    metadata: dict[str, str | int],
    root: Path,
) -> WorkspaceState:
    retained = enforce_retention(root=root, state=state).state
    persist_workspace_unlocked(root, retained)
    append_workspace_event(
        root=root,
        workspace_id=retained.workspace_id,
        event={
            "event_id": f"evt-{uuid4().hex[:8]}",
            "event_type": event_type,
            "workspace_id": retained.workspace_id,
            "created_at": now_iso(),
            "metadata": metadata,
        },
    )
    emit_workspace_audit_event(
        event_type=event_type,
        workspace_id=retained.workspace_id,
        summary=summary,
        metadata=metadata,
    )
    return retained
