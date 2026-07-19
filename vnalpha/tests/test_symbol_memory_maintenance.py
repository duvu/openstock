from __future__ import annotations

import gzip
from dataclasses import replace
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
from vnalpha.symbol_memory.retrieval import (
    MemoryContextBudget,
    SymbolMemoryRetrievalService,
)
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


def test_archived_events_do_not_keep_triggering_compaction_threshold(tmp_path) -> None:
    repository = _repository()
    repository.append_event(_event("event-001"))
    repository.append_event(_event("event-002"))
    from vnalpha.symbol_memory.archive import SymbolMemoryArchiveService

    SymbolMemoryArchiveService(repository, tmp_path).rotate("FPT")
    service = SymbolMemoryCompactionService(
        repository,
        tmp_path,
        policy=MemoryCompactionPolicy(uncompacted_event_threshold=1),
    )

    assert service.needs_compaction("FPT") is False


def test_retrieval_enforces_total_and_per_section_memory_budgets() -> None:
    repository = _repository()
    repository.create_claim(_claim("fact"))
    repository.create_claim(_claim("risk", claim_type="risk_or_caveat"))
    service = SymbolMemoryRetrievalService(repository)

    result = service.retrieve(
        "FPT",
        budget=MemoryContextBudget(
            total_tokens=1000,
            section_token_budgets={"risk": 1},
        ),
    )

    assert [claim.claim_id for claim in result.selected_claims] == ["fact"]
    assert ("risk", "section_budget:risk") in result.omitted_claims


def test_archive_rotation_compresses_events_without_deleting_evidence(tmp_path) -> None:
    repository = _repository()
    repository.append_event(_event("event-001"))
    repository.append_event(_event("event-002"))

    from vnalpha.symbol_memory.archive import SymbolMemoryArchiveService

    archive = SymbolMemoryArchiveService(repository, tmp_path)
    first = archive.rotate("FPT")
    second = archive.rotate("FPT")

    assert first.archived_event_count == 2
    assert second.archived_event_count == 0
    assert repository.list_events("FPT") == [_event("event-001"), _event("event-002")]
    assert first.path is not None
    with gzip.open(first.path, "rt", encoding="utf-8") as handle:
        assert "source:event-001" in handle.read()


def test_scheduled_maintenance_is_bounded_and_isolates_symbol_failures(
    tmp_path,
) -> None:
    repository = _repository()
    repository.create_claim(_claim("fpt-claim"))
    repository.create_claim(
        replace(
            _claim("hpg-claim"),
            symbol="HPG",
            source_refs=("source:hpg-claim",),
        )
    )
    corrupt_card = tmp_path / "knowledge" / "symbols" / "FPT.md"
    corrupt_card.parent.mkdir(parents=True)
    corrupt_card.write_text("invalid card", encoding="utf-8")

    from vnalpha.symbol_memory.maintenance import SymbolMemoryMaintenanceService

    service = SymbolMemoryMaintenanceService(repository, tmp_path)
    bounded = service.run(
        symbols=("FPT", "HPG"),
        as_of_date=date(2026, 7, 15),
        max_symbols=1,
    )
    result = service.run(
        symbols=("FPT", "HPG"),
        as_of_date=date(2026, 7, 15),
        max_symbols=2,
    )

    assert bounded.processed_symbols == ()
    assert bounded.failed_symbols == ("FPT",)
    assert result.processed_symbols == ("HPG",)
    assert result.failed_symbols == ("FPT",)
    assert (tmp_path / "knowledge/symbols/HPG.md").exists()


def test_ten_thousand_archived_events_do_not_expand_retrieval_budget(tmp_path) -> None:
    repository = _repository()
    repository.create_claim(_claim("active"))
    repository.connection.executemany(
        "INSERT INTO memory_event (event_id, symbol, event_type, evidence_ref, "
        "content_hash, observed_at, as_of_date, origin, correlation_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                f"event-{index}",
                "FPT",
                "EVIDENCE_OBSERVED",
                f"source:event-{index}",
                f"sha256:event-{index}",
                _timestamp(),
                date(2026, 7, 13),
                ClaimOrigin.VALIDATED_EVIDENCE.value,
                f"correlation:event-{index}",
                _timestamp(),
            )
            for index in range(10_000)
        ],
    )

    from vnalpha.symbol_memory.archive import SymbolMemoryArchiveService

    archived = SymbolMemoryArchiveService(repository, tmp_path).rotate("FPT")
    result = SymbolMemoryRetrievalService(repository).retrieve("FPT", token_budget=1)

    assert archived.archived_event_count == 10_000
    assert result.token_estimate <= 1


def test_archive_rotation_reaches_events_after_an_archived_page(tmp_path) -> None:
    repository = _repository()
    repository.connection.executemany(
        "INSERT INTO memory_event (event_id, symbol, event_type, evidence_ref, "
        "content_hash, observed_at, as_of_date, origin, correlation_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                f"event-{index:05d}",
                "FPT",
                "EVIDENCE_OBSERVED",
                f"source:event-{index:05d}",
                f"sha256:event-{index:05d}",
                _timestamp(),
                date(2026, 7, 13),
                ClaimOrigin.VALIDATED_EVIDENCE.value,
                f"correlation:event-{index:05d}",
                _timestamp(),
            )
            for index in range(10_001)
        ],
    )

    from vnalpha.symbol_memory.archive import SymbolMemoryArchiveService

    archive = SymbolMemoryArchiveService(repository, tmp_path)
    assert archive.rotate("FPT").archived_event_count == 10_000
    assert archive.rotate("FPT").archived_event_count == 1
