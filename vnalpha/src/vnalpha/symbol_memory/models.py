from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Mapping

from vnalpha.symbol_memory.paths import normalize_symbol


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


class MemoryEntityType(StrEnum):
    SYMBOL = "SYMBOL"
    MARKET = "MARKET"
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    ASSET_CLASS = "ASSET_CLASS"


_ENTITY_PART = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{0,63}$")


@dataclass(frozen=True, slots=True)
class MemoryEntity:
    entity_type: MemoryEntityType
    entity_id: str

    def __post_init__(self) -> None:
        canonical = self.entity_id.strip().upper()
        if self.entity_type is MemoryEntityType.SYMBOL:
            canonical = normalize_symbol(canonical)
        elif self.entity_type is MemoryEntityType.MARKET:
            if canonical != "VN":
                raise ValueError("The only supported market memory entity is VN.")
        elif not canonical or any(
            not _ENTITY_PART.fullmatch(part) for part in canonical.split(":")
        ):
            raise ValueError(
                "Memory entity identity is not a safe canonical identifier."
            )
        object.__setattr__(self, "entity_id", canonical)

    @classmethod
    def symbol(cls, symbol: str) -> MemoryEntity:
        return cls(MemoryEntityType.SYMBOL, symbol)

    @classmethod
    def market(cls, market_id: str = "VN") -> MemoryEntity:
        return cls(MemoryEntityType.MARKET, market_id)

    @classmethod
    def taxonomy(
        cls,
        entity_type: MemoryEntityType,
        *,
        code: str,
        taxonomy_name: str,
        taxonomy_version: str,
    ) -> MemoryEntity:
        if entity_type not in {MemoryEntityType.SECTOR, MemoryEntityType.INDUSTRY}:
            raise ValueError("Taxonomy entities must be sectors or industries.")
        return cls(
            entity_type,
            f"{taxonomy_name.strip()}:{taxonomy_version.strip()}:{code.strip()}",
        )

    @classmethod
    def asset_class(cls, security_type: str) -> MemoryEntity:
        return cls(MemoryEntityType.ASSET_CLASS, security_type)


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    event_id: str
    symbol: str | None
    event_type: str
    evidence_ref: str | None
    content_hash: str
    observed_at: datetime | None
    as_of_date: date | None
    origin: ClaimOrigin
    correlation_id: str
    created_at: datetime
    entity_type: MemoryEntityType = MemoryEntityType.SYMBOL
    entity_id: str | None = None

    @property
    def entity(self) -> MemoryEntity:
        return _resolve_entity(self.symbol, self.entity_type, self.entity_id)


@dataclass(frozen=True, slots=True)
class MemoryClaim:
    claim_id: str
    symbol: str | None
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
    entity_type: MemoryEntityType = MemoryEntityType.SYMBOL
    entity_id: str | None = None

    @property
    def entity(self) -> MemoryEntity:
        return _resolve_entity(self.symbol, self.entity_type, self.entity_id)


@dataclass(frozen=True, slots=True)
class MemoryDocument:
    symbol: str | None
    path: str
    schema_version: int
    generation: int
    managed_hash: str
    document_hash: str
    token_estimate: int
    last_compacted_at: datetime | None
    updated_at: datetime
    entity_type: MemoryEntityType = MemoryEntityType.SYMBOL
    entity_id: str | None = None

    @property
    def entity(self) -> MemoryEntity:
        return _resolve_entity(self.symbol, self.entity_type, self.entity_id)


@dataclass(frozen=True, slots=True)
class MemoryCompactionRun:
    compaction_run_id: str
    symbol: str | None
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
    entity_type: MemoryEntityType = MemoryEntityType.SYMBOL
    entity_id: str | None = None

    @property
    def entity(self) -> MemoryEntity:
        return _resolve_entity(self.symbol, self.entity_type, self.entity_id)


@dataclass(frozen=True, slots=True)
class MemoryRetrievalResult:
    symbol: str | None
    selected_claims: tuple[MemoryClaim, ...]
    omitted_claims: tuple[tuple[str, str], ...]
    token_estimate: int
    as_of_date: date | None
    source_coverage: float
    conflict_claim_ids: tuple[str, ...] = ()
    risk_claim_ids: tuple[str, ...] = ()
    caveat_claim_ids: tuple[str, ...] = ()
    missing_data_claim_ids: tuple[str, ...] = ()
    entity_type: MemoryEntityType = MemoryEntityType.SYMBOL
    entity_id: str | None = None

    @property
    def entity(self) -> MemoryEntity:
        return _resolve_entity(self.symbol, self.entity_type, self.entity_id)


def _resolve_entity(
    symbol: str | None,
    entity_type: MemoryEntityType,
    entity_id: str | None,
) -> MemoryEntity:
    resolved_id = entity_id or symbol
    if resolved_id is None:
        raise ValueError("Memory entity identity is required.")
    entity = MemoryEntity(entity_type, resolved_id)
    if symbol is not None and entity_type is MemoryEntityType.SYMBOL:
        if normalize_symbol(symbol) != entity.entity_id:
            raise ValueError("Symbol and entity identity must match.")
    return entity


__all__ = [
    "ClaimOrigin",
    "ClaimStatus",
    "MemoryEntity",
    "MemoryEntityType",
    "MemoryClaim",
    "MemoryCompactionRun",
    "MemoryDocument",
    "MemoryEvent",
    "MemoryRetrievalResult",
]
