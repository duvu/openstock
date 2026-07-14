from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable, TypeVar

import duckdb

from vnalpha.symbol_memory.archive import SymbolMemoryArchiveService
from vnalpha.symbol_memory.lifecycle import SymbolMemoryLifecycleService
from vnalpha.symbol_memory.locking import symbol_memory_lock
from vnalpha.symbol_memory.markdown import (
    atomic_write_text,
    parse_symbol_card,
    write_symbol_card,
)
from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryCompactionRun,
    MemoryEvent,
)
from vnalpha.symbol_memory.observability import emit_memory_lifecycle
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.symbol_memory.storage import assert_knowledge_path, symbol_card_path

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class MemoryCompactionPreview:
    symbol: str
    changed: bool
    retained_claim_count: int
    archived_claim_count: int
    conflicted_claim_count: int
    before_token_estimate: int
    after_token_estimate: int
    source_coverage: float
    managed_content: str


@dataclass(frozen=True, slots=True)
class MemoryCompactionPolicy:
    symbol_card_token_budget: int = 1600
    uncompacted_event_threshold: int = 100

    def __post_init__(self) -> None:
        if self.symbol_card_token_budget < 0:
            raise ValueError("Symbol-card token budget cannot be negative.")
        if self.uncompacted_event_threshold < 0:
            raise ValueError("Uncompacted event threshold cannot be negative.")


@dataclass(frozen=True, slots=True)
class MicroCompactionResult:
    expired_claim_ids: tuple[str, ...]
    preview: MemoryCompactionPreview


class SymbolMemoryCompactionService:
    def __init__(
        self,
        repository: SymbolMemoryRepository,
        root: Path | None,
        *,
        policy: MemoryCompactionPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.root = root
        self.retrieval = SymbolMemoryRetrievalService(repository)
        self.lifecycle = SymbolMemoryLifecycleService(repository)
        self.policy = policy or MemoryCompactionPolicy()

    def preview(
        self, symbol: str, *, token_budget: int | None = None
    ) -> MemoryCompactionPreview:
        result = self.retrieval.retrieve(
            symbol,
            token_budget=(
                self.policy.symbol_card_token_budget
                if token_budget is None
                else token_budget
            ),
        )
        selected_claims = list(result.selected_claims)
        selected_ids = {claim.claim_id for claim in selected_claims}
        selected_claims.extend(
            claim
            for claim in self.repository.list_claims(
                symbol, statuses=(ClaimStatus.REJECTED,), limit=1_000
            )
            if claim.claim_type == "rejected_hypothesis"
            and claim.claim_id not in selected_ids
        )
        managed_content = _render_claims(tuple(selected_claims))
        existing = self.repository.get_document(symbol)
        before_tokens = 0 if existing is None else existing.token_estimate
        archived_count = len(result.omitted_claims)
        conflicted_count = sum(
            1 for claim in selected_claims if claim.status.value == "conflicted"
        )
        changed = existing is None or existing.managed_hash != _hash(managed_content)
        return MemoryCompactionPreview(
            symbol=result.symbol,
            changed=changed,
            retained_claim_count=len(selected_claims),
            archived_claim_count=archived_count,
            conflicted_claim_count=conflicted_count,
            before_token_estimate=before_tokens,
            after_token_estimate=_estimate_tokens(managed_content),
            source_coverage=result.source_coverage,
            managed_content=managed_content,
        )

    def needs_compaction(self, symbol: str) -> bool:
        document = self.repository.get_document(symbol)
        return SymbolMemoryArchiveService(
            self.repository, self.root
        ).unarchived_event_count(symbol) > self.policy.uncompacted_event_threshold or (
            document is not None
            and document.token_estimate > self.policy.symbol_card_token_budget
        )

    def micro_compact(self, symbol: str, *, as_of_date: date) -> MicroCompactionResult:
        expired_claim_ids = self.lifecycle.expire_due_claims(
            symbol, as_of_date=as_of_date
        )
        return MicroCompactionResult(
            expired_claim_ids=expired_claim_ids,
            preview=self.compact(symbol),
        )

    def compact(
        self,
        symbol: str,
        *,
        token_budget: int | None = None,
        user_content: str | None = None,
    ) -> MemoryCompactionPreview:
        correlation_id = f"memory-compaction-{symbol.strip().upper()}"
        started_at = perf_counter()
        emit_memory_lifecycle(
            "MEMORY_COMPACTION_STARTED",
            symbol=symbol.strip().upper(),
            correlation_id=correlation_id,
        )
        try:
            with symbol_memory_lock(self.root, symbol):
                result = self._compact_unlocked(
                    symbol,
                    token_budget=token_budget,
                    user_content=user_content,
                )
        except (duckdb.Error, OSError, ValueError):
            timestamp = datetime.now(UTC)
            self.repository.append_event(
                MemoryEvent(
                    event_id=(
                        "memory-compaction-failed-"
                        f"{_hash(correlation_id + timestamp.isoformat())}"
                    ),
                    symbol=symbol.strip().upper(),
                    event_type="MEMORY_COMPACTION_FAILED",
                    evidence_ref=None,
                    content_hash=_hash(correlation_id),
                    observed_at=timestamp,
                    as_of_date=timestamp.date(),
                    origin=ClaimOrigin.USER_CORRECTION,
                    correlation_id=correlation_id,
                    created_at=timestamp,
                )
            )
            emit_memory_lifecycle(
                "MEMORY_COMPACTION_FAILED",
                symbol=symbol.strip().upper(),
                correlation_id=correlation_id,
                duration_ms=(perf_counter() - started_at) * 1_000,
            )
            raise
        claims = self.repository.list_claims(result.symbol)
        document = self.repository.get_document(result.symbol)
        claim_statuses: dict[str, int] = {}
        for claim in claims:
            claim_statuses[claim.status.value] = (
                claim_statuses.get(claim.status.value, 0) + 1
            )
        emit_memory_lifecycle(
            "MEMORY_COMPACTION_COMPLETED",
            symbol=result.symbol,
            correlation_id=correlation_id,
            claim_counts={
                "retained": result.retained_claim_count,
                "archived": result.archived_claim_count,
                "conflicted": result.conflicted_claim_count,
            },
            claim_statuses=claim_statuses,
            document_hash=None if document is None else document.document_hash,
            token_estimate=result.after_token_estimate,
            source_coverage=result.source_coverage,
            duration_ms=(perf_counter() - started_at) * 1_000,
        )
        return result

    def mutate_and_compact(
        self,
        symbol: str,
        mutation: Callable[[], T],
        *,
        user_content_factory: Callable[[str], str] | None = None,
    ) -> tuple[T, MemoryCompactionPreview]:
        with symbol_memory_lock(self.root, symbol):
            with self.repository.transaction():
                mutation_result = mutation()
                user_content = None
                if user_content_factory is not None:
                    card_path = symbol_card_path(self.root, symbol)
                    assert_knowledge_path(self.root, card_path)
                    existing_card = (
                        parse_symbol_card(card_path.read_text(encoding="utf-8"))
                        if card_path.exists()
                        else None
                    )
                    previous = (
                        "" if existing_card is None else existing_card.user_content
                    )
                    user_content = user_content_factory(previous)
                preview = self._compact_unlocked(symbol, user_content=user_content)
        return mutation_result, preview

    def _compact_unlocked(
        self,
        symbol: str,
        *,
        token_budget: int | None = None,
        user_content: str | None = None,
    ) -> MemoryCompactionPreview:
        preview = self.preview(symbol, token_budget=token_budget)
        card_path = symbol_card_path(self.root, symbol)
        assert_knowledge_path(self.root, card_path)
        previous = self.repository.get_document(symbol)
        previous_content = (
            card_path.read_text(encoding="utf-8") if card_path.exists() else None
        )
        existing_card = (
            parse_symbol_card(card_path.read_text(encoding="utf-8"))
            if card_path.exists()
            else None
        )
        expected_user_content = (
            existing_card.user_content
            if user_content is None and existing_card
            else user_content or ""
        )
        if (
            existing_card is not None
            and not preview.changed
            and existing_card.user_content == expected_user_content
        ):
            return preview
        timestamp = datetime.now(UTC)
        try:
            document = write_symbol_card(
                self.root,
                symbol,
                managed_content=preview.managed_content,
                user_content=expected_user_content,
                updated_at=timestamp,
            )
            self.repository.upsert_document(document)
            before_hash = "" if previous is None else previous.document_hash
            run = MemoryCompactionRun(
                compaction_run_id=f"memory-compaction-{_hash(document.document_hash)}",
                symbol=document.symbol,
                before_generation=max(0, document.generation - 1),
                after_generation=document.generation,
                before_hash=before_hash,
                after_hash=document.document_hash,
                retained_claim_count=preview.retained_claim_count,
                archived_claim_count=preview.archived_claim_count,
                conflicted_claim_count=preview.conflicted_claim_count,
                before_token_estimate=preview.before_token_estimate,
                after_token_estimate=document.token_estimate,
                source_coverage=preview.source_coverage,
                created_at=timestamp,
                correlation_id=f"memory-compaction-{document.symbol}",
            )
            self.repository.record_compaction_run(run)
        except (duckdb.Error, OSError, ValueError):
            if previous_content is None:
                card_path.unlink(missing_ok=True)
            else:
                atomic_write_text(card_path, previous_content)
            if previous is None:
                self.repository.delete_document(symbol)
            else:
                self.repository.upsert_document(previous)
            raise
        return MemoryCompactionPreview(
            symbol=preview.symbol,
            changed=True,
            retained_claim_count=preview.retained_claim_count,
            archived_claim_count=preview.archived_claim_count,
            conflicted_claim_count=preview.conflicted_claim_count,
            before_token_estimate=preview.before_token_estimate,
            after_token_estimate=document.token_estimate,
            source_coverage=preview.source_coverage,
            managed_content=preview.managed_content,
        )


def _render_claims(claims: tuple) -> str:
    if not claims:
        return "- No active structured claims."
    lines = []
    for claim in claims:
        value = ", ".join(
            f"{key}={value}" for key, value in sorted(claim.value.items())
        )
        sources = ", ".join(claim.source_refs) if claim.source_refs else "user-authored"
        lines.append(
            f"- `[claim:{claim.claim_id}]` {claim.predicate}: {value}  \n"
            f"  Sources: `{sources}`"
        )
    return "\n".join(lines)


def _estimate_tokens(content: str) -> int:
    return max(0, (len(content) + 3) // 4)


def _hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


__all__ = [
    "MemoryCompactionPolicy",
    "MemoryCompactionPreview",
    "MicroCompactionResult",
    "SymbolMemoryCompactionService",
]
