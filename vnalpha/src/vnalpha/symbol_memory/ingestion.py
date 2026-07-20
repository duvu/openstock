from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Mapping

from vnalpha.symbol_memory.lifecycle import SymbolMemoryLifecycleService
from vnalpha.symbol_memory.markdown import MemoryCardError, validate_symbol_card_content
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


_TRUSTED_EVIDENCE_SOURCE_KINDS = frozenset(
    {
        "candidate_score",
        "feature_snapshot",
        "canonical_ohlcv",
        "fundamental_fact",
        "valuation_snapshot",
        "symbol_event",
        "candidate_outcome",
        "research_market_regime_snapshot",
        "research_symbol_level_snapshot",
        "research_setup_analysis",
        "research_automation",
        "symbol_identity",
    }
)
_UNTRUSTED_SOURCE_TOKENS = frozenset({"assistant", "chat", "llm", "model"})


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
    source_published_at: date | None = None


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
        _validate_evidence(evidence, self.repository)
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
            source_published_at=evidence.source_published_at,
        )
        with self.repository.transaction():
            if not self.repository.append_event(event):
                return MemoryIngestionResult(created=False, claim=None)
            accepted = self.lifecycle.accept(claim)
        return MemoryIngestionResult(created=True, claim=accepted)

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
        try:
            validate_symbol_card_content(note)
        except MemoryCardError as exc:
            raise MemoryIngestionError(str(exc)) from exc
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
        with self.repository.transaction():
            if not self.repository.append_event(event):
                return MemoryIngestionResult(created=False, claim=None)
            accepted = self.lifecycle.accept(claim)
        return MemoryIngestionResult(created=True, claim=accepted)


def _validate_evidence(
    evidence: MemoryEvidence,
    repository: SymbolMemoryRepository,
) -> None:
    if not isinstance(evidence.observed_at, datetime) or not isinstance(
        evidence.as_of_date, date
    ):
        raise MemoryIngestionError("Memory evidence requires observed and as-of dates.")
    if not evidence.source_ref.strip():
        raise MemoryIngestionError(
            "Validated memory evidence requires a source reference."
        )
    source_kind, separator, source_identifier = evidence.source_ref.partition(":")
    source_kind = source_kind.strip().lower()
    source_tokens = frozenset(
        token
        for token in re.split(r"[^a-z0-9]+", evidence.source_ref.lower())
        if token
    )
    if _UNTRUSTED_SOURCE_TOKENS & source_tokens:
        raise MemoryIngestionError(
            "Raw assistant or chat content cannot become factual memory evidence."
        )
    if (
        not separator
        or not source_identifier.strip()
        or source_kind not in _TRUSTED_EVIDENCE_SOURCE_KINDS
    ):
        raise MemoryIngestionError(
            "Memory evidence requires a trusted persisted source kind."
        )
    if _contains_number(evidence.value) and (
        not isinstance(evidence.value.get("unit"), str)
        or not isinstance(evidence.value.get("meaning"), str)
    ):
        raise MemoryIngestionError(
            "Numeric memory evidence requires unit and semantic meaning."
        )
    if not repository.has_persisted_evidence(
        evidence.source_ref,
        evidence.symbol,
        evidence.as_of_date,
        evidence.claim_type,
        evidence.predicate,
        evidence.value,
    ):
        raise MemoryIngestionError(
            "Memory evidence does not match a persisted validated artifact."
        )
    if not evidence.claim_type or not evidence.predicate:
        raise MemoryIngestionError(
            "Memory evidence requires a claim type and predicate."
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


def _contains_number(value: Any) -> bool:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return True
    if isinstance(value, Mapping):
        return any(_contains_number(item) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_contains_number(item) for item in value)
    return False


def _identity(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "MemoryEvidence",
    "MemoryIngestionError",
    "MemoryIngestionResult",
    "SymbolMemoryIngestionService",
]
