from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb

from vnalpha.symbol_memory.ingestion import (
    MemoryEvidence,
    SymbolMemoryIngestionService,
)
from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def _service() -> SymbolMemoryIngestionService:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    connection.execute(
        "INSERT INTO candidate_score (symbol, date, score, candidate_class) "
        "VALUES ('FPT', '2026-07-13', 0.82, 'WATCH_CANDIDATE')"
    )
    return SymbolMemoryIngestionService(SymbolMemoryRepository(connection))


def _evidence() -> MemoryEvidence:
    return MemoryEvidence(
        symbol="FPT",
        claim_type="candidate_score",
        predicate="composite_score",
        value={
            "value": 0.82,
            "unit": "score",
            "meaning": "persisted composite candidate score",
        },
        source_ref="candidate_score:FPT:2026-07-13",
        observed_at=datetime(2026, 7, 13, 11, 0, tzinfo=timezone.utc),
        as_of_date=date(2026, 7, 13),
        confidence=0.82,
        correlation_id="ingestion-001",
    )


def test_validated_evidence_records_one_event_and_typed_claim_idempotently() -> None:
    service = _service()

    first = service.ingest_evidence(_evidence())
    second = service.ingest_evidence(_evidence())

    assert first.created is True
    assert second.created is False
    assert first.claim is not None
    assert first.claim.origin is ClaimOrigin.VALIDATED_EVIDENCE
    assert first.claim.status is ClaimStatus.ACTIVE
    assert service.repository.list_events("FPT")[0].evidence_ref.startswith(
        "candidate_score:"
    )
    assert len(service.repository.list_claims("FPT")) == 1
