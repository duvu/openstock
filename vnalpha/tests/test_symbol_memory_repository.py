from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb

from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
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
