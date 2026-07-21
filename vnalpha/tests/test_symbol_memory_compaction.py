from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb

from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus, MemoryClaim
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def _repository() -> SymbolMemoryRepository:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return SymbolMemoryRepository(connection)


def _claim(claim_id: str, *, status: ClaimStatus = ClaimStatus.ACTIVE) -> MemoryClaim:
    timestamp = datetime(2026, 7, 13, 13, 0, tzinfo=timezone.utc)
    return MemoryClaim(
        claim_id=claim_id,
        symbol="FPT",
        claim_type="candidate_score",
        predicate=claim_id,
        value={"value": 0.82, "unit": "score", "meaning": "composite score"},
        status=status,
        pinned=claim_id == "pinned",
        confidence=0.8,
        observed_at=timestamp,
        as_of_date=date(2026, 7, 13),
        valid_from=date(2026, 7, 13),
        valid_until=None,
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        source_refs=(f"source:{claim_id}",),
        correlation_id=f"compaction-{claim_id}",
        created_at=timestamp,
    )


def test_compaction_preview_is_non_mutating_and_reports_omissions(tmp_path) -> None:
    repository = _repository()
    repository.create_claim(_claim("active"))
    repository.create_claim(_claim("inactive", status=ClaimStatus.EXPIRED))
    service = SymbolMemoryCompactionService(repository, tmp_path)

    preview = service.preview("FPT", token_budget=1000)

    assert preview.changed is True
    assert preview.retained_claim_count == 1
    assert preview.archived_claim_count == 1
    assert repository.get_document("FPT") is None
    assert not (tmp_path / "knowledge/symbols/FPT.md").exists()
