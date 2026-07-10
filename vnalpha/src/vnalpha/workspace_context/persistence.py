from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from vnalpha.workspace_context.models import WorkspaceState
from vnalpha.workspace_context.observability import (
    WorkspaceAuditMetadata,
    emit_workspace_audit_event,
)
from vnalpha.workspace_context.storage import (
    append_workspace_event,
    save_latest_workspace_id,
    save_workspace_state,
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def append_lifecycle_event(
    *,
    root: Path | None,
    workspace_id: str,
    event_type: str,
    payload: WorkspaceAuditMetadata | None = None,
) -> None:
    append_workspace_event(
        root=root,
        workspace_id=workspace_id,
        event={
            "event_id": f"evt-{uuid4().hex[:8]}",
            "event_type": event_type,
            "workspace_id": workspace_id,
            "created_at": now_iso(),
            **(payload or {}),
        },
    )
    emit_workspace_audit_event(
        event_type=event_type,
        workspace_id=workspace_id,
        summary=f"Workspace event: {event_type}",
        metadata={"event_type": event_type},
    )


def persist_workspace(root: Path | None, state: WorkspaceState) -> WorkspaceState:
    save_workspace_state(root=root, state=state)
    save_latest_workspace_id(root=root, workspace_id=state.workspace_id)
    return state
