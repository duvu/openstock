from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb

from vnalpha.symbol_memory.compaction import (
    MemoryCompactionPolicy,
    SymbolMemoryCompactionService,
)
from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
    MemoryEvent,
)
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def _repository() -> SymbolMemoryRepository:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return SymbolMemoryRepository(connection)


def _timestamp() -> datetime:
    return datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _claim(claim_id: str, *, claim_type: str = "durable_fact") -> MemoryClaim:
    return MemoryClaim(
        claim_id=claim_id,
        symbol="FPT",
        claim_type=claim_type,
        predicate=claim_id,
        value={"state": "validated research evidence"},
        status=ClaimStatus.ACTIVE,
        pinned=False,
        confidence=None,
        observed_at=_timestamp(),
        as_of_date=date(2026, 7, 13),
        valid_from=date(2026, 7, 13),
        valid_until=None,
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        source_refs=(f"source:{claim_id}",),
        correlation_id=f"correlation:{claim_id}",
        created_at=_timestamp(),
    )


def _event(event_id: str) -> MemoryEvent:
    return MemoryEvent(
        event_id=event_id,
        symbol="FPT",
        event_type="EVIDENCE_OBSERVED",
        evidence_ref=f"source:{event_id}",
        content_hash=f"sha256:{event_id}",
        observed_at=_timestamp(),
        as_of_date=date(2026, 7, 13),
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        correlation_id=f"correlation:{event_id}",
        created_at=_timestamp(),
    )


def test_compaction_policy_controls_default_card_budget_and_event_threshold(
    tmp_path,
) -> None:
    repository = _repository()
    repository.create_claim(_claim("claim-001"))
    repository.append_event(_event("event-001"))
    repository.append_event(_event("event-002"))
    service = SymbolMemoryCompactionService(
        repository,
        tmp_path,
        policy=MemoryCompactionPolicy(
            symbol_card_token_budget=1,
            uncompacted_event_threshold=1,
        ),
    )

    preview = service.preview("FPT")

    assert preview.retained_claim_count == 0
    assert service.needs_compaction("FPT") is True
