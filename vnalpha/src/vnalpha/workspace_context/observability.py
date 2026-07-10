from __future__ import annotations

from vnalpha.observability.audit import log_audit

WorkspaceAuditMetadata = dict[str, str | int | float | bool]


def emit_workspace_audit_event(
    *,
    event_type: str,
    workspace_id: str,
    summary: str,
    metadata: WorkspaceAuditMetadata,
) -> None:
    log_audit(
        event_type,
        summary,
        extra=metadata,
        module="workspace_context",
        function="emit_workspace_audit_event",
        object_type="workspace",
        object_id=workspace_id,
    )
