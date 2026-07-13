from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
    MemoryEvent,
)
from vnalpha.symbol_memory.repository import SymbolMemoryRepository

_EXPIRY_DAYS: dict[str, int | None] = {
    "candidate_score": 1,
    "technical_observation": 5,
    "market_or_sector_context": 7,
    "periodic_fact": 90,
    "durable_fact": None,
    "hypothesis": 30,
    "rejected_hypothesis": None,
    "risk_or_caveat": 30,
    "data_quality_caveat": 7,
    "user_note": None,
    "open_question": 30,
}


class SymbolMemoryLifecycleService:
    def __init__(self, repository: SymbolMemoryRepository) -> None:
        self.repository = repository

    def accept(self, claim: MemoryClaim) -> MemoryClaim:
        active_claims = self.repository.list_claims(
            claim.symbol, statuses=(ClaimStatus.ACTIVE,)
        )
        matching = [
            existing
            for existing in active_claims
            if existing.predicate == claim.predicate
            and existing.claim_type == claim.claim_type
        ]
        equivalent = next(
            (existing for existing in matching if _equivalent(existing, claim)), None
        )
        if equivalent is not None:
            return equivalent
        accepted = claim
        for existing in matching:
            if _same_effective_date(existing, claim) and _authority(existing) == _authority(
                claim
            ):
                self._transition(
                    existing,
                    ClaimStatus.CONFLICTED,
                    "Equivalent-authority sources disagree for the same effective date.",
                )
                accepted = replace(
                    accepted,
                    status=ClaimStatus.CONFLICTED,
                    lifecycle_reason="Equivalent-authority conflict requires resolution.",
                )
            elif _is_newer(claim, existing) and _authority(claim) >= _authority(existing):
                self._transition(
                    existing,
                    ClaimStatus.SUPERSEDED,
                    f"Superseded by newer claim {claim.claim_id}.",
                )
                accepted = replace(
                    accepted,
                    supersedes_claim_id=existing.claim_id,
                )
            elif _authority(existing) > _authority(claim):
                accepted = replace(
                    accepted,
                    status=ClaimStatus.SUPERSEDED,
                    lifecycle_reason=(
                        f"Higher-authority active claim {existing.claim_id} remains current."
                    ),
                )
        self.repository.create_claim(accepted)
        return accepted

    def correct(self, claim_id: str, reason: str) -> None:
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise KeyError(f"Unknown memory claim: {claim_id}")
        self._transition(claim, ClaimStatus.REJECTED, reason)
        timestamp = datetime.now(UTC)
        self.repository.append_event(
            MemoryEvent(
                event_id=f"memory-correction-{_event_identity(claim, reason)}",
                symbol=claim.symbol,
                event_type="USER_CORRECTION_RECORDED",
                evidence_ref=claim.claim_id,
                content_hash=f"sha256:{_event_identity(claim, reason)}",
                observed_at=timestamp,
                as_of_date=timestamp.date(),
                origin=ClaimOrigin.USER_CORRECTION,
                correlation_id=claim.correlation_id,
                created_at=timestamp,
            )
        )

    def expire_due_claims(self, symbol: str, *, as_of_date: date) -> tuple[str, ...]:
        expired: list[str] = []
        for claim in self.repository.list_claims(symbol, statuses=(ClaimStatus.ACTIVE,)):
            expiry_date = _expiry_date(claim)
            if expiry_date is None or expiry_date >= as_of_date:
                continue
            self._transition(
                claim,
                ClaimStatus.EXPIRED,
                f"Expired after {expiry_date.isoformat()} under {claim.claim_type} policy.",
            )
            expired.append(claim.claim_id)
        return tuple(expired)

    def invalidate_sources(
        self,
        symbol: str,
        source_refs: set[str],
        *,
        reason: str,
    ) -> tuple[str, ...]:
        invalidated: list[str] = []
        for claim in self.repository.list_claims(symbol, statuses=(ClaimStatus.ACTIVE,)):
            if claim.source_refs and set(claim.source_refs).issubset(source_refs):
                self._transition(claim, ClaimStatus.REJECTED, reason)
                invalidated.append(claim.claim_id)
        return tuple(invalidated)

    def _transition(
        self, claim: MemoryClaim, status: ClaimStatus, reason: str
    ) -> None:
        self.repository.transition_claim(claim.claim_id, status, reason)


def _equivalent(left: MemoryClaim, right: MemoryClaim) -> bool:
    return (
        left.symbol == right.symbol
        and left.claim_type == right.claim_type
        and left.predicate == right.predicate
        and left.as_of_date == right.as_of_date
        and _canonical_value(left) == _canonical_value(right)
    )


def _canonical_value(claim: MemoryClaim) -> str:
    return json.dumps(claim.value, sort_keys=True, separators=(",", ":"), default=str)


def _authority(claim: MemoryClaim) -> int:
    if claim.origin is ClaimOrigin.USER_CORRECTION:
        return 100
    if claim.origin is ClaimOrigin.VALIDATED_EVIDENCE:
        return 80
    return 20


def _same_effective_date(left: MemoryClaim, right: MemoryClaim) -> bool:
    return left.as_of_date == right.as_of_date


def _is_newer(left: MemoryClaim, right: MemoryClaim) -> bool:
    if left.as_of_date is None:
        return False
    if right.as_of_date is None:
        return True
    return left.as_of_date > right.as_of_date


def _expiry_date(claim: MemoryClaim) -> date | None:
    if claim.valid_until is not None:
        return claim.valid_until
    days = _EXPIRY_DAYS.get(claim.claim_type, 30)
    if days is None or claim.as_of_date is None:
        return None
    return claim.as_of_date + timedelta(days=days)


def _event_identity(claim: MemoryClaim, reason: str) -> str:
    payload = f"{claim.claim_id}|{reason}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = ["SymbolMemoryLifecycleService"]
