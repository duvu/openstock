from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from vnalpha.symbol_memory.adapters import (
    CandidateStateSnapshot,
    candidate_state_evidence,
    taxonomy_identity_evidence,
)
from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.ingestion import (
    MemoryEvidence,
    MemoryIngestionError,
    SymbolMemoryIngestionService,
)
from vnalpha.symbol_memory.lifecycle import SymbolMemoryLifecycleService
from vnalpha.symbol_memory.models import ClaimStatus, MemoryClaim
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.symbol_lifecycle import get_symbol_taxonomy_as_of


@dataclass(frozen=True, slots=True)
class SelectiveProjectionCounters:
    claims_created: int = 0
    claims_superseded: int = 0
    claims_expired: int = 0
    claims_rejected: int = 0
    claims_conflicted: int = 0
    cards_compacted: int = 0

    def __add__(
        self, other: SelectiveProjectionCounters
    ) -> SelectiveProjectionCounters:
        return SelectiveProjectionCounters(
            claims_created=self.claims_created + other.claims_created,
            claims_superseded=self.claims_superseded + other.claims_superseded,
            claims_expired=self.claims_expired + other.claims_expired,
            claims_rejected=self.claims_rejected + other.claims_rejected,
            claims_conflicted=self.claims_conflicted + other.claims_conflicted,
            cards_compacted=self.cards_compacted + other.cards_compacted,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "claims_created": self.claims_created,
            "claims_superseded": self.claims_superseded,
            "claims_expired": self.claims_expired,
            "claims_rejected": self.claims_rejected,
            "claims_conflicted": self.claims_conflicted,
            "cards_compacted": self.cards_compacted,
        }


@dataclass(frozen=True, slots=True)
class SelectiveProjectionResult:
    counters: SelectiveProjectionCounters
    processed_symbols: tuple[str, ...]
    failed_symbols: tuple[str, ...]


class SelectiveSymbolMemoryProjector:
    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        memory_root: Path | None = None,
    ) -> None:
        self.conn = conn
        self.repository = SymbolMemoryRepository(conn)
        self.ingestion = SymbolMemoryIngestionService(self.repository)
        self.lifecycle = SymbolMemoryLifecycleService(self.repository)
        self.compaction = SymbolMemoryCompactionService(self.repository, memory_root)

    def project(
        self,
        symbols: tuple[str, ...],
        *,
        as_of_date: date,
        correlation_id: str,
    ) -> SelectiveProjectionResult:
        counters = SelectiveProjectionCounters()
        processed = []
        failed = []
        for raw_symbol in symbols:
            symbol = "INVALID_SYMBOL"
            try:
                symbol = normalize_symbol(raw_symbol)
                delta = self._project_symbol(
                    symbol,
                    as_of_date=as_of_date,
                    correlation_id=correlation_id,
                )
            except (MemoryIngestionError, OSError, ValueError, duckdb.Error):
                failed.append(symbol)
                continue
            counters += delta
            processed.append(symbol)
        return SelectiveProjectionResult(counters, tuple(processed), tuple(failed))

    def _project_symbol(
        self, symbol: str, *, as_of_date: date, correlation_id: str
    ) -> SelectiveProjectionCounters:
        before = self.repository.list_claims(symbol, limit=1_000)
        evidences = _validated_evidences(
            self.conn,
            symbol,
            as_of_date=as_of_date,
            correlation_id=correlation_id,
        )
        if not evidences and not before:
            return SelectiveProjectionCounters()

        def mutate() -> None:
            invalid_refs = _invalid_source_refs(self.repository, before)
            if invalid_refs:
                self.lifecycle.invalidate_sources(
                    symbol,
                    invalid_refs,
                    reason="Persisted source evidence is no longer valid.",
                )
            self.lifecycle.expire_due_claims(symbol, as_of_date=as_of_date)
            active = self.repository.list_claims(
                symbol, statuses=(ClaimStatus.ACTIVE,), limit=1_000
            )
            for evidence in evidences:
                if _semantically_current(active, evidence):
                    continue
                result = self.ingestion.ingest_evidence(evidence)
                if result.claim is not None:
                    active.append(result.claim)

        _, preview = self.compaction.mutate_and_compact(symbol, mutate)
        after = self.repository.list_claims(symbol, limit=1_000)
        before_counts = _status_counts(before)
        after_counts = _status_counts(after)
        return SelectiveProjectionCounters(
            claims_created=max(0, len(after) - len(before)),
            claims_superseded=_status_delta(
                before_counts, after_counts, ClaimStatus.SUPERSEDED
            ),
            claims_expired=_status_delta(
                before_counts, after_counts, ClaimStatus.EXPIRED
            ),
            claims_rejected=_status_delta(
                before_counts, after_counts, ClaimStatus.REJECTED
            ),
            claims_conflicted=_status_delta(
                before_counts, after_counts, ClaimStatus.CONFLICTED
            ),
            cards_compacted=int(preview.changed),
        )


def _validated_evidences(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    *,
    as_of_date: date,
    correlation_id: str,
) -> tuple[MemoryEvidence, ...]:
    observed_at = datetime.now(UTC)
    evidences = []
    taxonomy = get_symbol_taxonomy_as_of(conn, symbol, as_of_date)
    if taxonomy is not None:
        evidences.append(
            taxonomy_identity_evidence(
                taxonomy,
                correlation_id=correlation_id,
                observed_at=observed_at,
                as_of_date=as_of_date,
            )
        )
    row = conn.execute(
        "SELECT candidate_class, setup_type, risk_flags_json, "
        "scoring_policy_id, scoring_policy_hash, scoring_policy_status "
        "FROM candidate_score WHERE symbol = ? AND date = ?",
        [symbol, as_of_date],
    ).fetchone()
    if (
        row is not None
        and row[0]
        and row[3]
        and row[4]
        and str(row[5] or "").upper() in {"ACCEPTED", "EXPERIMENTAL"}
    ):
        evidences.append(
            candidate_state_evidence(
                CandidateStateSnapshot(
                    symbol=symbol,
                    as_of_date=as_of_date,
                    candidate_class=str(row[0]),
                    setup_type=None if row[1] is None else str(row[1]),
                    risk_flags=tuple(_risk_flag_codes(row[2])),
                    correlation_id=correlation_id,
                    persisted_at=observed_at,
                    scoring_policy_id=str(row[3]),
                    scoring_policy_hash=str(row[4]),
                )
            )
        )
    return tuple(evidences)


def _risk_flag_codes(value: object) -> list[str]:
    try:
        parsed = json.loads(str(value)) if isinstance(value, str) else value
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        raw = [key for key, enabled in parsed.items() if bool(enabled)]
    elif isinstance(parsed, list):
        raw = parsed
    else:
        return []
    return sorted({str(item).strip()[:80] for item in raw if str(item).strip()})[:20]


def _invalid_source_refs(
    repository: SymbolMemoryRepository, claims: list[MemoryClaim]
) -> set[str]:
    invalid = set()
    for claim in claims:
        if claim.status is not ClaimStatus.ACTIVE or claim.as_of_date is None:
            continue
        for source_ref in claim.source_refs:
            if not repository.has_persisted_evidence(
                source_ref,
                claim.symbol,
                claim.as_of_date,
                claim.claim_type,
                claim.predicate,
                claim.value,
            ):
                invalid.add(source_ref)
    return invalid


def _semantically_current(claims: list[MemoryClaim], evidence: MemoryEvidence) -> bool:
    target = json.dumps(
        dict(evidence.value), sort_keys=True, separators=(",", ":"), default=str
    )
    return any(
        claim.claim_type == evidence.claim_type
        and claim.predicate == evidence.predicate
        and json.dumps(
            dict(claim.value), sort_keys=True, separators=(",", ":"), default=str
        )
        == target
        for claim in claims
        if claim.status is ClaimStatus.ACTIVE
    )


def _status_counts(claims: list[MemoryClaim]) -> dict[ClaimStatus, int]:
    counts: dict[ClaimStatus, int] = {}
    for claim in claims:
        counts[claim.status] = counts.get(claim.status, 0) + 1
    return counts


def _status_delta(
    before: dict[ClaimStatus, int],
    after: dict[ClaimStatus, int],
    status: ClaimStatus,
) -> int:
    return max(0, after.get(status, 0) - before.get(status, 0))


__all__ = [
    "SelectiveProjectionCounters",
    "SelectiveProjectionResult",
    "SelectiveSymbolMemoryProjector",
]
