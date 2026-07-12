from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

from vnalpha.workspace_context.compaction import compact_workspace
from vnalpha.workspace_context.locking import workspace_transaction
from vnalpha.workspace_context.models import (
    WorkspaceResumeSummary,
    WorkspaceState,
    WorkspaceStatus,
    WorkspaceStatusReport,
)
from vnalpha.workspace_context.mutations import (
    record_artifact,
    record_error,
    record_input,
    record_warning,
)
from vnalpha.workspace_context.persistence import (
    append_lifecycle_event as _append_event,
)
from vnalpha.workspace_context.persistence import (
    now_iso as _now_iso,
)
from vnalpha.workspace_context.storage import (
    clear_latest_workspace_id,
    ensure_workspace_layout,
    load_latest_workspace_id,
    load_workspace_state,
    quarantine_latest_workspace_pointer,
    resolve_workspace_root,
    save_latest_workspace_id,
    save_workspace_state,
)

MAX_CONTEXT_EVENTS: Final = 100
MAX_CONTEXT_INPUTS: Final = 50
MAX_CONTEXT_ARTIFACTS: Final = 50


class WorkspaceLifecycleError(RuntimeError):
    def __init__(self, workspace_id: str, operation: str, reason: str) -> None:
        self.workspace_id = workspace_id
        self.operation = operation
        self.reason = reason
        super().__init__(reason)

    def __str__(self) -> str:
        return f"Cannot {self.operation} workspace {self.workspace_id}: {self.reason}"


__all__ = [
    "archive_workspace",
    "check_lifecycle_invariants",
    "create_workspace",
    "get_or_create_latest_workspace",
    "get_resume_summary",
    "get_status",
    "list_workspaces",
    "new_workspace",
    "record_artifact",
    "record_error",
    "record_input",
    "record_warning",
    "reactivate_workspace",
    "resume_workspace",
]


def _make_workspace_id() -> str:
    return f"ws-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:6]}"


def _default_title(workspace_id: str) -> str:
    return f"Workspace {workspace_id}"


def get_or_create_latest_workspace(root: Path | None = None) -> WorkspaceState:
    try:
        latest_id = load_latest_workspace_id(root=root)
    except json.JSONDecodeError:
        quarantine_latest_workspace_pointer(root=root)
        latest_id = None
    if latest_id is not None:
        try:
            latest = load_workspace_state(root=root, workspace_id=latest_id)
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            clear_latest_workspace_id(root=root)
        else:
            if latest.status == WorkspaceStatus.ACTIVE.value:
                return latest
            clear_latest_workspace_id(root=root)
    active = [
        state
        for state in list_workspaces(root=root)
        if state.status == WorkspaceStatus.ACTIVE.value
    ]
    if active:
        selected = active[0]
        save_latest_workspace_id(root=root, workspace_id=selected.workspace_id)
        return selected
    return create_workspace(root=root)


def create_workspace(
    title: str | None = None, mode: str | None = None, root: Path | None = None
) -> WorkspaceState:
    workspace_id = _make_workspace_id()
    now = _now_iso()
    resolved_root = resolve_workspace_root(root)
    ensure_workspace_layout(root=resolved_root, workspace_id=workspace_id)
    state = WorkspaceState(
        workspace_id=workspace_id,
        title=title or _default_title(workspace_id),
        status="active",
        mode=mode or "general",
        created_at=now,
        updated_at=now,
        context_size={"events": 1, "inputs": 0, "artifacts": 0},
    )
    with workspace_transaction(workspace_id, root=resolved_root):
        save_workspace_state(root=resolved_root, state=state)
        save_latest_workspace_id(root=resolved_root, workspace_id=workspace_id)
        _append_event(
            root=resolved_root,
            workspace_id=workspace_id,
            event_type="WORKSPACE_CREATED",
        )
    return state


def resume_workspace(
    workspace_id: str | None = None, root: Path | None = None
) -> WorkspaceState:
    resolved_root = resolve_workspace_root(root)
    target_id = workspace_id or load_latest_workspace_id(root=resolved_root)
    if target_id is None:
        return create_workspace(root=resolved_root)
    state = load_workspace_state(root=resolved_root, workspace_id=target_id)
    if state.status != WorkspaceStatus.ACTIVE.value:
        raise WorkspaceLifecycleError(
            target_id,
            "resume",
            f"workspace status is {state.status}; reactivate it explicitly first",
        )
    with workspace_transaction(target_id, root=resolved_root):
        save_latest_workspace_id(root=resolved_root, workspace_id=target_id)
        _append_event(
            root=resolved_root,
            workspace_id=target_id,
            event_type="WORKSPACE_RESUMED",
            payload={
                "mode": state.mode,
                "status": state.status,
                "active_symbol_count": len(state.active_symbols),
                "open_task_count": len(state.open_tasks),
            },
        )
    return state


def get_resume_summary(
    workspace_id: str | None = None, root: Path | None = None
) -> WorkspaceResumeSummary:
    state = resume_workspace(workspace_id=workspace_id, root=root)
    return WorkspaceResumeSummary(
        workspace_id=state.workspace_id,
        title=state.title,
        mode=state.mode,
        status=state.status,
        active_date=state.active_date,
        active_symbols=list(state.active_symbols),
        open_task_count=len(state.open_tasks),
        last_compacted_at=state.last_compacted_at,
        warnings=list(state.warnings),
        errors=list(state.errors),
    )


def new_workspace(
    *, no_compact: bool = False, root: Path | None = None
) -> WorkspaceState:
    resolved_root = resolve_workspace_root(root)
    previous_id = load_latest_workspace_id(root=resolved_root)
    if previous_id is not None:
        if not no_compact:
            compact_workspace(previous_id, root=resolved_root)
        archive_workspace(previous_id, root=resolved_root)
    current = create_workspace(root=resolved_root)
    _append_event(
        root=resolved_root,
        workspace_id=current.workspace_id,
        event_type="WORKSPACE_NEW_STARTED",
        payload={"previous_workspace_present": previous_id is not None},
    )
    return current


def list_workspaces(root: Path | None = None) -> list[WorkspaceState]:
    resolved_root = resolve_workspace_root(root)
    if not resolved_root.exists():
        return []
    states: list[WorkspaceState] = []
    for child in sorted(resolved_root.iterdir()):
        if not child.is_dir() or child.name == "archive":
            continue
        workspace_json = child / "workspace.json"
        if workspace_json.exists():
            try:
                states.append(
                    load_workspace_state(root=resolved_root, workspace_id=child.name)
                )
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
    return sorted(
        states, key=lambda state: (state.updated_at, state.workspace_id), reverse=True
    )


def check_lifecycle_invariants(root: Path | None = None) -> None:
    states = list_workspaces(root=root)
    active = [state for state in states if state.status == WorkspaceStatus.ACTIVE.value]
    latest_id = load_latest_workspace_id(root=root)
    if len(active) > 1:
        raise WorkspaceLifecycleError(
            "*",
            "validate lifecycle",
            "more than one active workspace exists",
        )
    if active and latest_id != active[0].workspace_id:
        raise WorkspaceLifecycleError(
            active[0].workspace_id,
            "validate lifecycle",
            "latest pointer does not reference the active workspace",
        )
    if latest_id is not None and not any(
        state.workspace_id == latest_id and state.status == WorkspaceStatus.ACTIVE.value
        for state in states
    ):
        raise WorkspaceLifecycleError(
            latest_id,
            "validate lifecycle",
            "latest pointer does not reference a valid active workspace",
        )


def archive_workspace(workspace_id: str, root: Path | None = None) -> WorkspaceState:
    resolved_root = resolve_workspace_root(root)
    state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    if state.status != WorkspaceStatus.ACTIVE.value:
        raise WorkspaceLifecycleError(
            workspace_id,
            "archive",
            f"workspace status is {state.status}",
        )
    archived = WorkspaceState.from_dict(
        {
            **state.to_dict(),
            "status": "archived",
            "updated_at": _now_iso(),
        }
    )
    with workspace_transaction(workspace_id, root=resolved_root):
        save_workspace_state(root=resolved_root, state=archived)
        if load_latest_workspace_id(root=resolved_root) == workspace_id:
            clear_latest_workspace_id(root=resolved_root)
        _append_event(
            root=resolved_root,
            workspace_id=workspace_id,
            event_type="WORKSPACE_ARCHIVED",
        )
    return archived


def reactivate_workspace(workspace_id: str, root: Path | None = None) -> WorkspaceState:
    resolved_root = resolve_workspace_root(root)
    state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    if state.status != WorkspaceStatus.ARCHIVED.value:
        raise WorkspaceLifecycleError(
            workspace_id,
            "reactivate",
            f"workspace status is {state.status}",
        )
    reactivated = WorkspaceState.from_dict(
        {
            **state.to_dict(),
            "status": WorkspaceStatus.ACTIVE.value,
            "updated_at": _now_iso(),
        }
    )
    with workspace_transaction(workspace_id, root=resolved_root):
        save_workspace_state(root=resolved_root, state=reactivated)
        save_latest_workspace_id(root=resolved_root, workspace_id=workspace_id)
        _append_event(
            root=resolved_root,
            workspace_id=workspace_id,
            event_type="WORKSPACE_REACTIVATED",
        )
    return reactivated


def get_status(
    workspace_id: str | None = None, root: Path | None = None
) -> WorkspaceStatusReport:
    resolved_root = resolve_workspace_root(root)
    if workspace_id is None:
        state = get_or_create_latest_workspace(root=resolved_root)
    else:
        state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    stale_artifacts = [
        artifact.artifact_id
        for artifact in state.active_artifacts
        if not (resolved_root / state.workspace_id / artifact.path).exists()
    ]
    exceeds_context_threshold = (
        state.context_size.get("events", 0) >= MAX_CONTEXT_EVENTS
        or state.context_size.get("inputs", 0) >= MAX_CONTEXT_INPUTS
        or state.context_size.get("artifacts", 0) >= MAX_CONTEXT_ARTIFACTS
    )
    should_compact = (
        bool(stale_artifacts) or exceeds_context_threshold or bool(state.warnings)
    )
    return WorkspaceStatusReport(
        workspace_id=state.workspace_id,
        title=state.title,
        mode=state.mode,
        status=state.status,
        active_date=state.active_date,
        active_symbols=list(state.active_symbols),
        open_tasks=[task.text for task in state.open_tasks],
        warnings=list(state.warnings),
        errors=list(state.errors),
        last_updated_at=state.updated_at,
        last_compacted_at=state.last_compacted_at,
        context_size=dict(state.context_size),
        stale_artifacts=stale_artifacts,
        suggested_action="/context compact" if should_compact else None,
        source_refs=["workspace.json"],
    )
