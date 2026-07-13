from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb

from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus, MemoryClaim
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.warehouse.migrations import run_migrations


def _repository() -> SymbolMemoryRepository:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return SymbolMemoryRepository(connection)


def _claim(
    claim_id: str,
    *,
    symbol: str = "FPT",
    as_of_date: date = date(2026, 7, 13),
    status: ClaimStatus = ClaimStatus.ACTIVE,
    pinned: bool = False,
) -> MemoryClaim:
    return MemoryClaim(
        claim_id=claim_id,
        symbol=symbol,
        claim_type="candidate_score",
        predicate=claim_id,
        value={"value": 0.82, "unit": "score", "meaning": "composite score"},
        status=status,
        pinned=pinned,
        confidence=0.8,
        observed_at=datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc),
        as_of_date=as_of_date,
        valid_from=as_of_date,
        valid_until=None,
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        source_refs=(f"source:{claim_id}",),
        correlation_id=f"retrieval-{claim_id}",
        created_at=datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc),
    )


def test_retrieval_is_exact_symbol_temporal_and_status_safe() -> None:
    repository = _repository()
    repository.create_claim(_claim("active"))
    repository.create_claim(_claim("future", as_of_date=date(2026, 7, 14)))
    repository.create_claim(_claim("expired", status=ClaimStatus.EXPIRED))
    repository.create_claim(_claim("other", symbol="HPG"))
    service = SymbolMemoryRetrievalService(repository)

    result = service.retrieve("FPT", as_of_date=date(2026, 7, 13), token_budget=1000)

    assert [claim.claim_id for claim in result.selected_claims] == ["active"]
    assert set(result.omitted_claims) == {
        ("expired", "inactive"),
        ("future", "future"),
    }
    assert result.as_of_date == date(2026, 7, 13)
    assert result.source_coverage == 1.0


def test_retrieval_respects_whole_claim_budget_and_marks_context_untrusted() -> None:
    repository = _repository()
    repository.create_claim(_claim("pinned", pinned=True))
    repository.create_claim(_claim("normal"))
    service = SymbolMemoryRetrievalService(repository)

    result = service.retrieve("FPT", token_budget=1)
    context = service.render_context(result)

    assert [claim.claim_id for claim in result.selected_claims] == []
    assert {claim_id for claim_id, _ in result.omitted_claims} == {"pinned", "normal"}
    assert "untrusted historical reference" in context
