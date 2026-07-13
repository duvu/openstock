from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Mapping


class ClaimStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    REJECTED = "rejected"
    CONFLICTED = "conflicted"


class ClaimOrigin(StrEnum):
    VALIDATED_EVIDENCE = "validated_evidence"
    USER_NOTE = "user_note"
    USER_CORRECTION = "user_correction"


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    event_id: str
    symbol: str
    event_type: str
    evidence_ref: str | None
    content_hash: str
    observed_at: datetime | None
    as_of_date: date | None
    origin: ClaimOrigin
    correlation_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryClaim:
    claim_id: str
    symbol: str
    claim_type: str
    predicate: str
    value: Mapping[str, Any]
    status: ClaimStatus
    pinned: bool
    confidence: float | None
    observed_at: datetime | None
    as_of_date: date | None
    valid_from: date | None
    valid_until: date | None
    origin: ClaimOrigin
    source_refs: tuple[str, ...]
    correlation_id: str
    created_at: datetime
    supersedes_claim_id: str | None = None
    lifecycle_reason: str | None = None
    source_published_at: date | None = None


@dataclass(frozen=True, slots=True)
class MemoryDocument:
    symbol: str
    path: str
    schema_version: int
    generation: int
    managed_hash: str
    document_hash: str
    token_estimate: int
    last_compacted_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryCompactionRun:
    compaction_run_id: str
    symbol: str
    before_generation: int
    after_generation: int
    before_hash: str
    after_hash: str
    retained_claim_count: int
    archived_claim_count: int
    conflicted_claim_count: int
    before_token_estimate: int
    after_token_estimate: int
    source_coverage: float
    created_at: datetime
    correlation_id: str


@dataclass(frozen=True, slots=True)
class MemoryRetrievalResult:
    symbol: str
    selected_claims: tuple[MemoryClaim, ...]
    omitted_claims: tuple[tuple[str, str], ...]
    token_estimate: int
    as_of_date: date | None
    source_coverage: float
    conflict_claim_ids: tuple[str, ...] = ()
    risk_claim_ids: tuple[str, ...] = ()
    caveat_claim_ids: tuple[str, ...] = ()
    missing_data_claim_ids: tuple[str, ...] = ()


__all__ = [
    "ClaimOrigin",
    "ClaimStatus",
    "MemoryClaim",
    "MemoryCompactionRun",
    "MemoryDocument",
    "MemoryEvent",
    "MemoryRetrievalResult",
]
