from __future__ import annotations

from typing import Any

from vnalpha.observability.audit import log_audit


def emit_research_event(
    event_type: str,
    *,
    artifact_id: str,
    correlation_id: str,
    status: str = "OK",
    extra: dict[str, Any] | None = None,
) -> None:
    metadata = {
        "artifact_id": artifact_id,
        "research_correlation_id": correlation_id,
        **(extra or {}),
    }
    log_audit(
        event_type,
        f"Research lifecycle event for {artifact_id}",
        status=status,
        extra=metadata,
    )


__all__ = ["emit_research_event"]
