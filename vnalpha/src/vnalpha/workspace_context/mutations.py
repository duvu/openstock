from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from vnalpha.observability.redaction import redact_str, redaction_status
from vnalpha.workspace_context.models import (
    WorkspaceArtifactRef,
    WorkspaceInputRef,
    WorkspaceState,
)
from vnalpha.workspace_context.persistence import (
    append_lifecycle_event,
    now_iso,
    persist_workspace_unlocked,
    workspace_mutation,
)
from vnalpha.workspace_context.retention import enforce_retention


def record_input(
    workspace: WorkspaceState,
    text: str,
    input_kind: str,
    source: str = "tui",
    *,
    root: Path | None = None,
) -> None:
    with workspace_mutation(workspace.workspace_id, root=root) as (
        resolved_root,
        current,
    ):
        now = now_iso()
        redacted_text = redact_str(text, mode="redacted")
        input_ref = WorkspaceInputRef(
            input_id=f"input-{uuid4().hex[:8]}",
            input_kind=input_kind,
            summary=redacted_text,
            redaction_status=redaction_status("redacted"),
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
        updated = enforce_retention(root=resolved_root, state=updated).state
        persist_workspace_unlocked(resolved_root, updated)
        append_lifecycle_event(
            root=resolved_root,
            workspace_id=current.workspace_id,
            event_type="WORKSPACE_INPUT_ADDED",
            payload={"input_kind": input_kind, "source": source},
        )


def record_artifact(
    workspace: WorkspaceState,
    artifact_ref: WorkspaceArtifactRef,
    *,
    root: Path | None = None,
) -> None:
    with workspace_mutation(workspace.workspace_id, root=root) as (
        resolved_root,
        current,
    ):
        now = now_iso()
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
        updated = enforce_retention(root=resolved_root, state=updated).state
        persist_workspace_unlocked(resolved_root, updated)
        append_lifecycle_event(
            root=resolved_root,
            workspace_id=current.workspace_id,
            event_type="WORKSPACE_ARTIFACT_ADDED",
            payload={"artifact_id": artifact_ref.artifact_id},
        )


def record_warning(
    workspace: WorkspaceState, warning: str, *, root: Path | None = None
) -> None:
    _record_message(
        workspace, warning, "warnings", "WORKSPACE_CONTEXT_UPDATED", root=root
    )


def record_error(
    workspace: WorkspaceState, error: str, *, root: Path | None = None
) -> None:
    _record_message(workspace, error, "errors", "WORKSPACE_ERROR", root=root)


def _record_message(
    workspace: WorkspaceState,
    message: str,
    field_name: str,
    event_type: str,
    *,
    root: Path | None,
) -> None:
    with workspace_mutation(workspace.workspace_id, root=root) as (
        resolved_root,
        current,
    ):
        now = now_iso()
        values = [*getattr(current, field_name), redact_str(message, mode="redacted")]
        updated = WorkspaceState.from_dict(
            {
                **current.to_dict(),
                "updated_at": now,
                field_name: values,
                "context_size": {
                    **current.context_size,
                    "events": current.context_size.get("events", 0) + 1,
                },
            }
        )
        updated = enforce_retention(root=resolved_root, state=updated).state
        persist_workspace_unlocked(resolved_root, updated)
        append_lifecycle_event(
            root=resolved_root,
            workspace_id=current.workspace_id,
            event_type=event_type,
            payload={f"{field_name[:-1]}_count": len(values)},
        )
