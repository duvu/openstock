from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from vnalpha.observability.redaction import redact_str, redaction_status
from vnalpha.workspace_context.models import (
    WorkspaceArtifactRef,
    WorkspaceInputRef,
    WorkspaceState,
    WorkspaceStatusReport,
)
from vnalpha.workspace_context.storage import (
    append_workspace_event,
    ensure_workspace_layout,
    load_latest_workspace_id,
    load_workspace_state,
    resolve_workspace_root,
    save_latest_workspace_id,
    save_workspace_state,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _make_workspace_id() -> str:
    return f"ws-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:6]}"


def _default_title(workspace_id: str) -> str:
    return f"Workspace {workspace_id}"


def _append_event(
    *, root, workspace_id: str, event_type: str, payload: dict[str, object] | None = None
) -> None:
    append_workspace_event(
        root=root,
        workspace_id=workspace_id,
        event={
            "event_id": f"evt-{uuid4().hex[:8]}",
            "event_type": event_type,
            "workspace_id": workspace_id,
            "created_at": _now_iso(),
            **(payload or {}),
        },
    )


def _persist(root, state: WorkspaceState) -> WorkspaceState:
    save_workspace_state(root=root, state=state)
    save_latest_workspace_id(root=root, workspace_id=state.workspace_id)
    return state


def get_or_create_latest_workspace(root=None) -> WorkspaceState:
    latest_id = load_latest_workspace_id(root=root)
    if latest_id is not None:
        return load_workspace_state(root=root, workspace_id=latest_id)
    return create_workspace(root=root)


def create_workspace(
    title: str | None = None, mode: str | None = None, root=None
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
    _persist(resolved_root, state)
    _append_event(
        root=resolved_root,
        workspace_id=workspace_id,
        event_type="WORKSPACE_CREATED",
        payload={"title": state.title, "mode": state.mode},
    )
    return state


def resume_workspace(workspace_id: str | None = None, root=None) -> WorkspaceState:
    resolved_root = resolve_workspace_root(root)
    target_id = workspace_id or load_latest_workspace_id(root=resolved_root)
    if target_id is None:
        return create_workspace(root=resolved_root)
    state = load_workspace_state(root=resolved_root, workspace_id=target_id)
    save_latest_workspace_id(root=resolved_root, workspace_id=target_id)
    return state


def list_workspaces(root=None) -> list[WorkspaceState]:
    resolved_root = resolve_workspace_root(root)
    if not resolved_root.exists():
        return []
    states: list[WorkspaceState] = []
    for child in sorted(resolved_root.iterdir()):
        if not child.is_dir() or child.name == "archive":
            continue
        workspace_json = child / "workspace.json"
        if workspace_json.exists():
            states.append(load_workspace_state(root=resolved_root, workspace_id=child.name))
    return states


def archive_workspace(workspace_id: str, root=None) -> WorkspaceState:
    resolved_root = resolve_workspace_root(root)
    state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    archived = WorkspaceState.from_dict({
        **state.to_dict(),
        "status": "archived",
        "updated_at": _now_iso(),
    })
    _persist(resolved_root, archived)
    _append_event(
        root=resolved_root,
        workspace_id=workspace_id,
        event_type="WORKSPACE_ARCHIVED",
    )
    return archived


def get_status(workspace_id: str | None = None, root=None) -> WorkspaceStatusReport:
    state = resume_workspace(workspace_id=workspace_id, root=root)
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
        stale_artifacts=[],
        suggested_action="/context compact" if state.warnings else None,
        source_refs=["workspace.json"],
    )


def record_input(
    workspace: WorkspaceState,
    text: str,
    input_kind: str,
    source: str = "tui",
    *,
    root=None,
) -> None:
    resolved_root = resolve_workspace_root(root)
    current = load_workspace_state(root=resolved_root, workspace_id=workspace.workspace_id)
    now = _now_iso()
    redacted_text = redact_str(text)
    input_ref = WorkspaceInputRef(
        input_id=f"input-{uuid4().hex[:8]}",
        input_kind=input_kind,
        summary=redacted_text,
        redaction_status=redaction_status(),
        created_at=now,
        source=source,
        content=redacted_text,
        metadata={"length": len(text)},
    )
    updated = WorkspaceState.from_dict(
        {
            **current.to_dict(),
            "updated_at": now,
            "recent_inputs": [
                *[item.to_dict() for item in current.recent_inputs],
                input_ref.to_dict(),
            ],
            "context_size": {
                **current.context_size,
                "inputs": len(current.recent_inputs) + 1,
                "events": current.context_size.get("events", 0) + 1,
            },
        }
    )
    _persist(resolved_root, updated)
    _append_event(
        root=resolved_root,
        workspace_id=current.workspace_id,
        event_type="WORKSPACE_INPUT_ADDED",
        payload={"input_kind": input_kind, "source": source},
    )


def record_artifact(
    workspace: WorkspaceState, artifact_ref: WorkspaceArtifactRef, *, root=None
) -> None:
    resolved_root = resolve_workspace_root(root)
    current = load_workspace_state(root=resolved_root, workspace_id=workspace.workspace_id)
    now = _now_iso()
    updated = WorkspaceState.from_dict(
        {
            **current.to_dict(),
            "updated_at": now,
            "active_artifacts": [
                *[item.to_dict() for item in current.active_artifacts],
                artifact_ref.to_dict(),
            ],
            "context_size": {
                **current.context_size,
                "artifacts": len(current.active_artifacts) + 1,
                "events": current.context_size.get("events", 0) + 1,
            },
        }
    )
    _persist(resolved_root, updated)
    _append_event(
        root=resolved_root,
        workspace_id=current.workspace_id,
        event_type="WORKSPACE_ARTIFACT_ADDED",
        payload={"artifact_id": artifact_ref.artifact_id},
    )


def record_warning(workspace: WorkspaceState, warning: str, *, root=None) -> None:
    resolved_root = resolve_workspace_root(root)
    current = load_workspace_state(root=resolved_root, workspace_id=workspace.workspace_id)
    now = _now_iso()
    updated = WorkspaceState.from_dict(
        {
            **current.to_dict(),
            "updated_at": now,
            "warnings": [*current.warnings, warning],
            "context_size": {
                **current.context_size,
                "events": current.context_size.get("events", 0) + 1,
            },
        }
    )
    _persist(resolved_root, updated)
    _append_event(
        root=resolved_root,
        workspace_id=current.workspace_id,
        event_type="WORKSPACE_CONTEXT_UPDATED",
        payload={"warning": warning},
    )


def record_error(workspace: WorkspaceState, error: str, *, root=None) -> None:
    resolved_root = resolve_workspace_root(root)
    current = load_workspace_state(root=resolved_root, workspace_id=workspace.workspace_id)
    now = _now_iso()
    updated = WorkspaceState.from_dict(
        {
            **current.to_dict(),
            "updated_at": now,
            "errors": [*current.errors, error],
            "context_size": {
                **current.context_size,
                "events": current.context_size.get("events", 0) + 1,
            },
        }
    )
    _persist(resolved_root, updated)
    _append_event(
        root=resolved_root,
        workspace_id=current.workspace_id,
        event_type="WORKSPACE_ERROR",
        payload={"error": error},
    )
