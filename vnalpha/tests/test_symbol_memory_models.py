from __future__ import annotations

from datetime import date, datetime, timezone

from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
    MemoryCompactionRun,
    MemoryDocument,
    MemoryEvent,
    MemoryRetrievalResult,
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
        observed_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
        as_of_date=date(2026, 7, 10),
        valid_from=date(2026, 7, 10),
        valid_until=date(2026, 7, 11),
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        source_refs=("candidate_score:FPT:2026-07-10",),
        correlation_id="corr-memory-001",
        created_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )


def test_memory_contracts_preserve_typed_temporal_metadata() -> None:
    claim = _claim()
    event = MemoryEvent(
        event_id="event-001",
        symbol="FPT",
        event_type="EVIDENCE_ACCEPTED",
        evidence_ref="candidate_score:FPT:2026-07-10",
        content_hash="hash-001",
        observed_at=claim.observed_at,
        as_of_date=claim.as_of_date,
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        correlation_id=claim.correlation_id,
        created_at=claim.created_at,
    )
    document = MemoryDocument(
        symbol="FPT",
        path="knowledge/symbols/FPT.md",
        schema_version=1,
        generation=3,
        managed_hash="managed-001",
        document_hash="document-001",
        token_estimate=42,
        last_compacted_at=claim.created_at,
        updated_at=claim.created_at,
    )
    compaction = MemoryCompactionRun(
        compaction_run_id="compact-001",
        symbol="FPT",
        before_generation=2,
        after_generation=3,
        before_hash="before-001",
        after_hash="after-001",
        retained_claim_count=1,
        archived_claim_count=0,
        conflicted_claim_count=0,
        before_token_estimate=54,
        after_token_estimate=42,
        source_coverage=1.0,
        created_at=claim.created_at,
        correlation_id=claim.correlation_id,
    )
    retrieval = MemoryRetrievalResult(
        symbol="FPT",
        selected_claims=(claim,),
        omitted_claims=(("claim-002", "budget"),),
        token_estimate=42,
        as_of_date=date(2026, 7, 10),
        source_coverage=1.0,
    )

    assert event.symbol == claim.symbol
    assert document.generation == compaction.after_generation
    assert retrieval.selected_claims == (claim,)
