from __future__ import annotations

import logging


def test_memory_lifecycle_logs_are_bounded_redacted_and_correlated(caplog) -> None:
    from vnalpha.symbol_memory.observability import emit_memory_lifecycle

    with caplog.at_level(logging.INFO, logger="vnalpha.symbol_memory"):
        payload = emit_memory_lifecycle(
            "MEMORY_COMPACTION_COMPLETED",
            symbol="FPT",
            correlation_id="correlation-001",
            claim_counts={"active": 2},
            claim_statuses={"active": 2},
            document_hash="sha256:document",
            token_estimate=123,
            source_coverage=1.0,
            duration_ms=12.5,
            note="private note body",
        )

    assert payload["correlation_id"] == "correlation-001"
    assert payload["claim_counts"] == {"active": 2}
    assert payload["claim_statuses"] == {"active": 2}
    assert payload["document_hash"] == "sha256:document"
    assert payload["duration_ms"] == 12.5
    assert "note" not in payload
    assert "private note body" not in caplog.text
