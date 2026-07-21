from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb

from vnalpha.symbol_memory.lifecycle import SymbolMemoryLifecycleService
from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus, MemoryClaim
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def _repository() -> SymbolMemoryRepository:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return SymbolMemoryRepository(connection)


def _claim(
    claim_id: str,
    *,
    value: float = 0.82,
    as_of_date: date = date(2026, 7, 12),
    origin: ClaimOrigin = ClaimOrigin.VALIDATED_EVIDENCE,
    valid_until: date | None = None,
) -> MemoryClaim:
    timestamp = datetime(2026, 7, 12, 9, 0, tzinfo=timezone.utc)
    return MemoryClaim(
        claim_id=claim_id,
        symbol="FPT",
        claim_type="candidate_score",
        predicate="composite_score",
        value={"value": value, "unit": "score", "meaning": "composite score"},
        status=ClaimStatus.ACTIVE,
        pinned=False,
        confidence=0.8,
        observed_at=timestamp,
        as_of_date=as_of_date,
        valid_from=as_of_date,
        valid_until=valid_until,
        origin=origin,
        source_refs=(f"candidate_score:FPT:{as_of_date.isoformat()}",),
        correlation_id=f"correlation-{claim_id}",
        created_at=timestamp,
    )


def test_newer_validated_claim_supersedes_older_active_claim() -> None:
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    older = _claim("claim-old")
    newer = _claim("claim-new", value=0.91, as_of_date=date(2026, 7, 13))

    service.accept(older)
    accepted = service.accept(newer)

    assert accepted.status is ClaimStatus.ACTIVE
    assert repository.get_claim(older.claim_id).status is ClaimStatus.SUPERSEDED
    assert repository.get_claim(newer.claim_id).supersedes_claim_id == older.claim_id
