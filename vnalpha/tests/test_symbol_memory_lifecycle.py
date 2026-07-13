from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

import duckdb
import pytest

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


def test_same_authority_conflict_keeps_both_claims_visible_for_resolution() -> None:
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    first = _claim("claim-first")
    conflicting = _claim("claim-conflict", value=0.44)

    service.accept(first)
    accepted = service.accept(conflicting)

    assert accepted.status is ClaimStatus.CONFLICTED
    assert repository.get_claim(first.claim_id).status is ClaimStatus.CONFLICTED
    assert len(repository.list_claims("FPT", statuses=(ClaimStatus.CONFLICTED,))) == 2


def test_correction_resolves_a_two_claim_conflict_and_records_the_resolution() -> None:
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    first = _claim("claim-first")
    second = _claim("claim-second", value=0.44)
    service.accept(first)
    service.accept(second)

    service.correct(first.claim_id, "The first source was stale.")

    assert repository.get_claim(first.claim_id).status is ClaimStatus.REJECTED
    assert repository.get_claim(second.claim_id).status is ClaimStatus.ACTIVE
    assert {event.event_type for event in repository.list_events("FPT")} == {
        "USER_CORRECTION_RECORDED",
        "MEMORY_CONFLICT_RESOLVED",
    }


def test_same_date_higher_authority_evidence_supersedes_lower_authority_claim() -> None:
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    lower = replace(_claim("lower"), source_refs=("research_automation:run-1",))
    higher = replace(
        _claim("higher", value=0.91),
        source_refs=("candidate_score:FPT:2026-07-12",),
    )

    service.accept(lower)
    accepted = service.accept(higher)

    assert accepted.status is ClaimStatus.ACTIVE
    assert repository.get_claim(lower.claim_id).status is ClaimStatus.SUPERSEDED
    assert accepted.supersedes_claim_id == lower.claim_id


def test_equivalent_claim_merges_and_user_correction_preserves_audit_events() -> None:
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    first = _claim("claim-first")

    service.accept(first)
    merged = service.accept(replace(first, claim_id="claim-duplicate"))
    service.correct(first.claim_id, "User correction: source was stale.")

    assert merged.claim_id == first.claim_id
    assert repository.get_claim(first.claim_id).status is ClaimStatus.REJECTED
    assert [event.event_type for event in repository.list_events("FPT")] == [
        "USER_CORRECTION_RECORDED"
    ]


def test_correction_rolls_back_claim_transition_when_audit_event_fails(
    monkeypatch,
) -> None:
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    claim = _claim("claim-atomic-correction")
    service.accept(claim)

    monkeypatch.setattr(repository, "append_event", lambda _event: False)

    with pytest.raises(RuntimeError, match="audit event"):
        service.correct(claim.claim_id, "Audit event must be durable.")

    assert repository.get_claim(claim.claim_id).status is ClaimStatus.ACTIVE


def test_claim_expiry_uses_claim_type_specific_policy_and_keeps_user_notes_active() -> (
    None
):
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    score = _claim("claim-score")
    note = _claim("claim-note", origin=ClaimOrigin.USER_NOTE)
    note = replace(
        note,
        claim_type="user_note",
        predicate="user_note",
        value={"note": "Keep reviewing the source."},
        source_refs=(),
    )

    service.accept(score)
    service.accept(note)
    expired = service.expire_due_claims("FPT", as_of_date=date(2026, 7, 15))

    assert expired == (score.claim_id,)
    assert repository.get_claim(score.claim_id).status is ClaimStatus.EXPIRED
    assert repository.get_claim(note.claim_id).status is ClaimStatus.ACTIVE


def test_source_invalidation_rejects_active_claim_and_preserves_rejected_hypothesis() -> (
    None
):
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    supported = _claim("claim-supported")
    hypothesis = replace(
        _claim("claim-rejected-hypothesis"),
        claim_type="rejected_hypothesis",
        predicate="rejected_thesis",
        status=ClaimStatus.REJECTED,
    )

    repository.create_claim(supported)
    repository.create_claim(hypothesis)
    invalidated = service.invalidate_sources(
        "FPT",
        set(supported.source_refs),
        reason="All supporting sources were invalidated.",
    )

    assert invalidated == (supported.claim_id,)
    assert repository.get_claim(supported.claim_id).status is ClaimStatus.REJECTED
    assert repository.get_claim(hypothesis.claim_id) == hypothesis
    assert [event.event_type for event in repository.list_events("FPT")] == [
        "SOURCE_INVALIDATED"
    ]


def test_user_correction_does_not_rewrite_canonical_warehouse_evidence() -> None:
    repository = _repository()
    service = SymbolMemoryLifecycleService(repository)
    claim = _claim("claim-corrected")
    repository.connection.execute(
        "CREATE TABLE canonical_evidence (source_ref VARCHAR PRIMARY KEY, value DOUBLE)"
    )
    repository.connection.execute(
        "INSERT INTO canonical_evidence VALUES (?, ?)",
        [claim.source_refs[0], 0.82],
    )
    service.accept(claim)

    service.correct(claim.claim_id, "User reported an inconsistency.")

    assert repository.get_claim(claim.claim_id).status is ClaimStatus.REJECTED
    assert repository.connection.execute(
        "SELECT value FROM canonical_evidence WHERE source_ref = ?",
        [claim.source_refs[0]],
    ).fetchone() == (0.82,)
