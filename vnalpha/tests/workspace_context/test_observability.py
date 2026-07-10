from __future__ import annotations

import json

from vnalpha.observability.context import (
    init_run_context,
    reset_run_context,
    set_correlation_id,
)
from vnalpha.workspace_context.observability import emit_workspace_audit_event


def test_emit_workspace_audit_event_redacts_sensitive_metadata(tmp_path) -> None:
    reset_run_context()
    run_context = init_run_context(surface="cli", actor="test", log_root=tmp_path)
    set_correlation_id()

    emit_workspace_audit_event(
        event_type="WORKSPACE_CONTEXT_UPDATED",
        workspace_id="ws-20260709-001",
        summary="Workspace context updated",
        metadata={"input_length": 23, "api_key": "top-secret"},
    )

    record = json.loads(run_context.audit_path.read_text(encoding="utf-8").strip())
    assert record["event_type"] == "WORKSPACE_CONTEXT_UPDATED"
    assert record["object_id"] == "ws-20260709-001"
    assert record["metadata"]["input_length"] == 23
    assert record["metadata"]["api_key"] == "[REDACTED]"
    reset_run_context()
