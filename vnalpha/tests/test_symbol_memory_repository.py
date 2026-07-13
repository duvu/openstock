from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb

from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
    MemoryCompactionRun,
    MemoryDocument,
    MemoryEvent,
)
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def _time() -> datetime:
    return datetime(2026, 7, 13, 9, 30, tzinfo=timezone.utc)


def _event() -> MemoryEvent:
    return MemoryEvent(
        event_id="event-001",
        symbol="FPT",
        event_type="EVIDENCE_OBSERVED",
        evidence_ref="candidate_score:FPT:2026-07-13",
        content_hash="event-content-001",
        observed_at=_time(),
        as_of_date=date(2026, 7, 13),
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        correlation_id="memory-correlation-001",
        created_at=_time(),
    )


def _claim() -> MemoryClaim:
    return MemoryClaim(
        claim_id="claim-001",
        symbol="FPT",
        claim_type="candidate_score",
        predicate="composite_score",
        value={"value": 0.82, "unit": "score"},
        status=ClaimStatus.ACTIVE,
        pinned=False,
        confidence=0.82,
        observed_at=_time(),
        as_of_date=date(2026, 7, 13),
        valid_from=date(2026, 7, 13),
        valid_until=date(2026, 7, 14),
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        source_refs=("candidate_score:FPT:2026-07-13",),
        correlation_id="memory-correlation-001",
        created_at=_time(),
    )


def _repository() -> SymbolMemoryRepository:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    run_migrations(connection)
    return SymbolMemoryRepository(connection)


def test_migrations_create_all_symbol_memory_tables_idempotently() -> None:
    repository = _repository()
    rows = repository.connection.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name LIKE 'memory_%' "
        "ORDER BY table_name"
    ).fetchall()

    assert [row[0] for row in rows] == [
        "memory_claim",
        "memory_compaction_run",
        "memory_document",
        "memory_event",
    ]


def test_events_are_append_only_and_deduplicated_by_evidence_and_content() -> None:
    repository = _repository()
    event = _event()

    assert repository.append_event(event) is True
    assert repository.append_event(event) is False
    assert repository.list_events("fpt") == [event]


def test_claim_creation_lookup_and_lifecycle_transition_preserve_history() -> None:
    repository = _repository()
    claim = _claim()

    repository.create_claim(claim)
    repository.transition_claim(
        claim.claim_id,
        ClaimStatus.SUPERSEDED,
        "newer validated evidence",
    )

    stored = repository.get_claim(claim.claim_id)
    assert stored is not None
    assert stored.status is ClaimStatus.SUPERSEDED
    assert stored.lifecycle_reason == "newer validated evidence"
    assert repository.list_claims("FPT", statuses=(ClaimStatus.ACTIVE,)) == []
    assert repository.list_claims("FPT") == [stored]


def test_document_and_compaction_metadata_round_trip() -> None:
    repository = _repository()
    document = MemoryDocument(
        symbol="FPT",
        path="knowledge/symbols/FPT.md",
        schema_version=1,
        generation=2,
        managed_hash="managed-002",
        document_hash="document-002",
        token_estimate=38,
        last_compacted_at=_time(),
        updated_at=_time(),
    )
    run = MemoryCompactionRun(
        compaction_run_id="compaction-001",
        symbol="FPT",
        before_generation=1,
        after_generation=2,
        before_hash="document-001",
        after_hash="document-002",
        retained_claim_count=2,
        archived_claim_count=1,
        conflicted_claim_count=0,
        before_token_estimate=52,
        after_token_estimate=38,
        source_coverage=1.0,
        created_at=_time(),
        correlation_id="memory-correlation-001",
    )

    repository.upsert_document(document)
    repository.record_compaction_run(run)

    assert repository.get_document("fpt") == document
    assert repository.list_compaction_runs("FPT") == [run]
