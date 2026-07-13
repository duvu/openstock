from __future__ import annotations

import logging
from collections.abc import Mapping

_LOGGER = logging.getLogger("vnalpha.symbol_memory")


def emit_memory_lifecycle(
    event_type: str,
    *,
    symbol: str,
    correlation_id: str,
    claim_counts: Mapping[str, int] | None = None,
    claim_statuses: Mapping[str, int] | None = None,
    document_hash: str | None = None,
    token_estimate: int | None = None,
    source_coverage: float | None = None,
    duration_ms: float | None = None,
    **_unsafe_metadata: str,
) -> dict[str, str | int | float | dict[str, int]]:
    payload: dict[str, str | int | float | dict[str, int]] = {
        "event_type": event_type,
        "symbol": symbol,
        "correlation_id": correlation_id,
    }
    if claim_counts is not None:
        payload["claim_counts"] = {
            str(status): int(count) for status, count in claim_counts.items()
        }
    if claim_statuses is not None:
        payload["claim_statuses"] = {
            str(status): int(count) for status, count in claim_statuses.items()
        }
    if document_hash is not None:
        payload["document_hash"] = document_hash
    if token_estimate is not None:
        payload["token_estimate"] = max(0, token_estimate)
    if source_coverage is not None:
        payload["source_coverage"] = max(0.0, min(1.0, source_coverage))
    if duration_ms is not None:
        payload["duration_ms"] = max(0.0, duration_ms)
    _LOGGER.info(event_type, extra={"memory_lifecycle": payload})
    return payload


__all__ = ["emit_memory_lifecycle"]
