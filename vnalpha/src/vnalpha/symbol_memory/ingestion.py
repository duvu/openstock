from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Mapping

from vnalpha.symbol_memory.lifecycle import SymbolMemoryLifecycleService
from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
    MemoryEvent,
)
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.validators import MemoryValidationError, validate_claim


class MemoryIngestionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MemoryEvidence:
    symbol: str
    claim_type: str
    predicate: str
    value: Mapping[str, Any]
    source_ref: str
    observed_at: datetime
    as_of_date: date
    confidence: float | None
    correlation_id: str


@dataclass(frozen=True, slots=True)
class MemoryIngestionResult:
    created: bool
    claim: MemoryClaim | None


class SymbolMemoryIngestionService:
    def __init__(
        self,
        repository: SymbolMemoryRepository,
        lifecycle: SymbolMemoryLifecycleService | None = None,
    ) -> None:
        self.repository = repository
        self.lifecycle = lifecycle or SymbolMemoryLifecycleService(repository)

    def ingest_evidence(self, evidence: MemoryEvidence) -> MemoryIngestionResult:
        _validate_evidence(evidence)
        symbol = normalize_symbol(evidence.symbol)
        identity = _identity(
            {
                "symbol": symbol,
                "claim_type": evidence.claim_type,
                "predicate": evidence.predicate,
                "value": evidence.value,
                "source_ref": evidence.source_ref,
                "as_of_date": evidence.as_of_date.isoformat(),
            }
        )
        event = MemoryEvent(
            event_id=f"memory-event-{identity}",
            symbol=symbol,
            event_type="EVIDENCE_OBSERVED",
            evidence_ref=evidence.source_ref,
            content_hash=f"sha256:{identity}",
            observed_at=evidence.observed_at,
            as_of_date=evidence.as_of_date,
            origin=ClaimOrigin.VALIDATED_EVIDENCE,
            correlation_id=evidence.correlation_id,
            created_at=evidence.observed_at,
        )
        if not self.repository.append_event(event):
            return MemoryIngestionResult(created=False, claim=None)
        claim = MemoryClaim(
            claim_id=f"memory-claim-{identity}",
            symbol=symbol,
            claim_type=evidence.claim_type,
            predicate=evidence.predicate,
            value=evidence.value,
            status=ClaimStatus.ACTIVE,
            pinned=False,
            confidence=evidence.confidence,
            observed_at=evidence.observed_at,
            as_of_date=evidence.as_of_date,
            valid_from=evidence.as_of_date,
            valid_until=None,
            origin=ClaimOrigin.VALIDATED_EVIDENCE,
            source_refs=(evidence.source_ref,),
            correlation_id=evidence.correlation_id,
            created_at=evidence.observed_at,
        )
        return MemoryIngestionResult(created=True, claim=self.lifecycle.accept(claim))

    def remember(
        self,
        symbol: str,
        note: str,
        *,
        correlation_id: str,
        created_at: datetime | None = None,
    ) -> MemoryIngestionResult:
        if not note.strip():
            raise MemoryIngestionError("A memory note cannot be empty.")
        timestamp = created_at or datetime.now(UTC)
        canonical_symbol = normalize_symbol(symbol)
        identity = _identity(
            {
                "symbol": canonical_symbol,
                "note": note,
                "correlation_id": correlation_id,
            }
        )
        event = MemoryEvent(
            event_id=f"memory-note-event-{identity}",
            symbol=canonical_symbol,
            event_type="USER_NOTE_RECORDED",
            evidence_ref=None,
            content_hash=f"sha256:{identity}",
            observed_at=timestamp,
            as_of_date=timestamp.date(),
            origin=ClaimOrigin.USER_NOTE,
            correlation_id=correlation_id,
            created_at=timestamp,
        )
        if not self.repository.append_event(event):
            return MemoryIngestionResult(created=False, claim=None)
        claim = MemoryClaim(
            claim_id=f"memory-note-claim-{identity}",
            symbol=canonical_symbol,
            claim_type="user_note",
            predicate="user_note",
            value={"note": note},
            status=ClaimStatus.ACTIVE,
            pinned=False,
            confidence=None,
            observed_at=timestamp,
            as_of_date=timestamp.date(),
            valid_from=timestamp.date(),
            valid_until=None,
            origin=ClaimOrigin.USER_NOTE,
            source_refs=(),
            correlation_id=correlation_id,
            created_at=timestamp,
        )
        return MemoryIngestionResult(created=True, claim=self.lifecycle.accept(claim))


def _validate_evidence(evidence: MemoryEvidence) -> None:
    if not evidence.source_ref.strip():
        raise MemoryIngestionError("Validated memory evidence requires a source reference.")
    if not evidence.claim_type or not evidence.predicate:
        raise MemoryIngestionError("Memory evidence requires a claim type and predicate.")
    if not isinstance(evidence.observed_at, datetime) or not isinstance(
        evidence.as_of_date, date
    ):
        raise MemoryIngestionError("Memory evidence requires observed and as-of dates.")
    if _contains_number(evidence.value) and (
        not isinstance(evidence.value.get("unit"), str)
        or not isinstance(evidence.value.get("meaning"), str)
    ):
        raise MemoryIngestionError(
            "Numeric memory evidence requires unit and semantic meaning."
        )
    try:
        validate_claim(
            MemoryClaim(
                claim_id="memory-validation",
                symbol=evidence.symbol,
                claim_type=evidence.claim_type,
                predicate=evidence.predicate,
                value=evidence.value,
                status=ClaimStatus.ACTIVE,
                pinned=False,
                confidence=evidence.confidence,
                observed_at=evidence.observed_at,
                as_of_date=evidence.as_of_date,
                valid_from=evidence.as_of_date,
                valid_until=None,
                origin=ClaimOrigin.VALIDATED_EVIDENCE,
                source_refs=(evidence.source_ref,),
                correlation_id=evidence.correlation_id,
                created_at=evidence.observed_at,
            )
        )
    except MemoryValidationError as exc:
        raise MemoryIngestionError(str(exc)) from exc


def _contains_number(value: Mapping[str, Any]) -> bool:
    return any(isinstance(item, int | float) and not isinstance(item, bool) for item in value.values())


def _identity(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "MemoryEvidence",
    "MemoryIngestionError",
    "MemoryIngestionResult",
    "SymbolMemoryIngestionService",
]
