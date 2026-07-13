from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.markdown import parse_symbol_card
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


def test_compaction_renders_from_claims_preserves_user_region_and_is_idempotent(
    tmp_path,
) -> None:
    repository = _repository()
    repository.create_claim(_claim("pinned"))
    service = SymbolMemoryCompactionService(repository, tmp_path)

    first = service.compact("FPT", token_budget=1000, user_content="Keep this note.\n")
    second = service.compact("FPT", token_budget=1000)
    document = repository.get_document("FPT")
    parsed = parse_symbol_card((tmp_path / document.path).read_text(encoding="utf-8"))

    assert first.changed is True
    assert second.changed is False
    assert parsed.user_content == "Keep this note.\n"
    assert "pinned" in parsed.managed_content
    assert len(repository.list_compaction_runs("FPT")) == 1


def test_micro_compaction_expires_due_claims_and_refreshes_only_that_symbol(
    tmp_path,
) -> None:
    repository = _repository()
    repository.create_claim(_claim("expiring"))
    service = SymbolMemoryCompactionService(repository, tmp_path)

    result = service.micro_compact("FPT", as_of_date=date(2026, 7, 15))

    assert result.expired_claim_ids == ("expiring",)
    assert repository.get_claim("expiring").status is ClaimStatus.EXPIRED
    assert (tmp_path / "knowledge/symbols/FPT.md").exists()


def test_compaction_rolls_back_the_card_when_document_indexing_fails(
    tmp_path, monkeypatch
) -> None:
    repository = _repository()
    repository.create_claim(_claim("active"))
    service = SymbolMemoryCompactionService(repository, tmp_path)

    def fail_indexing(_document) -> None:
        raise duckdb.Error("index write failed")

    monkeypatch.setattr(repository, "upsert_document", fail_indexing)

    with pytest.raises(duckdb.Error, match="index write failed"):
        service.compact("FPT")

    assert repository.get_document("FPT") is None
    assert not (tmp_path / "knowledge/symbols/FPT.md").exists()
