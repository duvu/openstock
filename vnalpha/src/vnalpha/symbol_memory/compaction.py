from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vnalpha.symbol_memory.markdown import parse_symbol_card, write_symbol_card
from vnalpha.symbol_memory.models import MemoryCompactionRun
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.symbol_memory.storage import symbol_card_path


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


class SymbolMemoryCompactionService:
    def __init__(self, repository: SymbolMemoryRepository, root: Path | None) -> None:
        self.repository = repository
        self.root = root
        self.retrieval = SymbolMemoryRetrievalService(repository)

    def preview(self, symbol: str, *, token_budget: int = 1600) -> MemoryCompactionPreview:
        result = self.retrieval.retrieve(symbol, token_budget=token_budget)
        managed_content = _render_claims(result.selected_claims)
        existing = self.repository.get_document(symbol)
        before_tokens = 0 if existing is None else existing.token_estimate
        archived_count = len(result.omitted_claims)
        conflicted_count = sum(
            1 for claim in result.selected_claims if claim.status.value == "conflicted"
        )
        changed = existing is None or existing.managed_hash != _hash(managed_content)
        return MemoryCompactionPreview(
            symbol=result.symbol,
            changed=changed,
            retained_claim_count=len(result.selected_claims),
            archived_claim_count=archived_count,
            conflicted_claim_count=conflicted_count,
            before_token_estimate=before_tokens,
            after_token_estimate=_estimate_tokens(managed_content),
            source_coverage=result.source_coverage,
            managed_content=managed_content,
        )

    def compact(
        self,
        symbol: str,
        *,
        token_budget: int = 1600,
        user_content: str | None = None,
    ) -> MemoryCompactionPreview:
        preview = self.preview(symbol, token_budget=token_budget)
        card_path = symbol_card_path(self.root, symbol)
        previous = self.repository.get_document(symbol)
        existing_card = (
            parse_symbol_card(card_path.read_text(encoding="utf-8"))
            if card_path.exists()
            else None
        )
        expected_user_content = (
            existing_card.user_content if user_content is None and existing_card else user_content or ""
        )
        if (
            existing_card is not None
            and not preview.changed
            and existing_card.user_content == expected_user_content
        ):
            return preview
        timestamp = datetime.now(UTC)
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
        value = ", ".join(f"{key}={value}" for key, value in sorted(claim.value.items()))
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


__all__ = ["MemoryCompactionPreview", "SymbolMemoryCompactionService"]
