from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.symbol_memory.ingestion import (
    MemoryEvidence,
    MemoryIngestionError,
    SymbolMemoryIngestionService,
)
from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def _service() -> SymbolMemoryIngestionService:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return SymbolMemoryIngestionService(SymbolMemoryRepository(connection))


def _evidence() -> MemoryEvidence:
    return MemoryEvidence(
        symbol="FPT",
        claim_type="candidate_score",
        predicate="composite_score",
        value={"value": 0.82, "unit": "score", "meaning": "composite score"},
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


def test_user_note_is_explicit_and_not_promoted_to_validated_fact() -> None:
    service = _service()

    result = service.remember(
        "FPT",
        "Watch whether relative strength broadens.",
        correlation_id="note-001",
        created_at=datetime(2026, 7, 13, 11, 0, tzinfo=timezone.utc),
    )

    assert result.claim is not None
    assert result.claim.claim_type == "user_note"
    assert result.claim.origin is ClaimOrigin.USER_NOTE
    assert result.claim.source_refs == ()


def test_numeric_evidence_requires_source_time_and_semantic_metadata() -> None:
    service = _service()
    invalid = replace(_evidence(), value={"value": 0.82}, source_ref="")

    with pytest.raises(MemoryIngestionError):
        service.ingest_evidence(invalid)
