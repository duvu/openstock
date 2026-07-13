from __future__ import annotations

import logging
from datetime import UTC, datetime

import duckdb
import pytest

from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus, MemoryClaim
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


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


def test_compaction_emits_redacted_lifecycle_events(tmp_path, monkeypatch) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    repository = SymbolMemoryRepository(connection)
    repository.create_claim(
        MemoryClaim(
            claim_id="claim-001",
            symbol="FPT",
            claim_type="durable_fact",
            predicate="research_state",
            value={"state": "watch"},
            status=ClaimStatus.ACTIVE,
            pinned=False,
            confidence=None,
            observed_at=None,
            as_of_date=None,
            valid_from=None,
            valid_until=None,
            origin=ClaimOrigin.USER_NOTE,
            source_refs=(),
            correlation_id="correlation-001",
            created_at=datetime.now(UTC),
        )
    )
    events: list[tuple[str, dict[str, object]]] = []

    def capture(event_type: str, **payload: object) -> dict[str, object]:
        events.append((event_type, payload))
        return payload

    monkeypatch.setattr(
        "vnalpha.symbol_memory.compaction.emit_memory_lifecycle", capture
    )

    SymbolMemoryCompactionService(repository, tmp_path).compact(
        "FPT", user_content="private note body"
    )

    assert [event_type for event_type, _ in events] == [
        "MEMORY_COMPACTION_STARTED",
        "MEMORY_COMPACTION_COMPLETED",
    ]
    assert "private note body" not in str(events)


def test_compaction_emits_failure_telemetry_for_filesystem_errors(
    tmp_path, monkeypatch
) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    repository = SymbolMemoryRepository(connection)
    events: list[str] = []

    monkeypatch.setattr(
        "vnalpha.symbol_memory.compaction.emit_memory_lifecycle",
        lambda event_type, **_payload: events.append(event_type),
    )
    monkeypatch.setattr(
        "vnalpha.symbol_memory.compaction.write_symbol_card",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )

    with pytest.raises(OSError, match="disk unavailable"):
        SymbolMemoryCompactionService(repository, tmp_path).compact("FPT")

    assert events == ["MEMORY_COMPACTION_STARTED", "MEMORY_COMPACTION_FAILED"]
