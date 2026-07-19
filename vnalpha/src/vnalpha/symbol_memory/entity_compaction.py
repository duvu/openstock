from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vnalpha.symbol_memory.locking import entity_memory_lock
from vnalpha.symbol_memory.markdown import atomic_write_text
from vnalpha.symbol_memory.models import (
    MemoryCompactionRun,
    MemoryDocument,
    MemoryEntity,
    MemoryEntityType,
)
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.symbol_memory.storage import assert_knowledge_path, entity_card_path


@dataclass(frozen=True, slots=True)
class EntityCompactionResult:
    entity: MemoryEntity
    changed: bool
    path: Path
    generation: int
    retained_claim_count: int
    token_estimate: int


class EntityMemoryCompactionService:
    def __init__(self, repository: SymbolMemoryRepository, root: Path | None) -> None:
        self.repository = repository
        self.root = root
        self.retrieval = SymbolMemoryRetrievalService(repository)

    def compact(
        self, entity: MemoryEntity, *, token_budget: int = 1_600
    ) -> EntityCompactionResult:
        with entity_memory_lock(self.root, entity):
            retrieval = self.retrieval.retrieve_entity(
                entity, token_budget=token_budget
            )
            managed = _managed_content(retrieval.selected_claims)
            managed_hash = _hash(managed)
            path = entity_card_path(self.root, entity)
            assert_knowledge_path(self.root, path)
            previous = self.repository.get_entity_document(entity)
            if previous is not None and previous.managed_hash == managed_hash:
                return EntityCompactionResult(
                    entity,
                    False,
                    path,
                    previous.generation,
                    len(retrieval.selected_claims),
                    previous.token_estimate,
                )
            timestamp = datetime.now(UTC)
            generation = 1 if previous is None else previous.generation + 1
            content = _render_card(entity, generation, managed, timestamp)
            document_hash = _hash(content)
            token_estimate = max(0, (len(managed) + 3) // 4)
            atomic_write_text(path, content)
            relative_path = path.relative_to(path.parents[2])
            document = MemoryDocument(
                symbol=(
                    entity.entity_id
                    if entity.entity_type is MemoryEntityType.SYMBOL
                    else None
                ),
                path=str(relative_path),
                schema_version=1,
                generation=generation,
                managed_hash=managed_hash,
                document_hash=document_hash,
                token_estimate=token_estimate,
                last_compacted_at=timestamp,
                updated_at=timestamp,
                entity_type=entity.entity_type,
                entity_id=entity.entity_id,
            )
            self.repository.upsert_document(document)
            self.repository.record_compaction_run(
                MemoryCompactionRun(
                    compaction_run_id=(
                        "entity-compaction-"
                        + hashlib.sha256(
                            f"{entity.entity_type}:{entity.entity_id}:{document_hash}".encode()
                        ).hexdigest()
                    ),
                    symbol=document.symbol,
                    before_generation=0 if previous is None else previous.generation,
                    after_generation=generation,
                    before_hash="" if previous is None else previous.document_hash,
                    after_hash=document_hash,
                    retained_claim_count=len(retrieval.selected_claims),
                    archived_claim_count=len(retrieval.omitted_claims),
                    conflicted_claim_count=len(retrieval.conflict_claim_ids),
                    before_token_estimate=(
                        0 if previous is None else previous.token_estimate
                    ),
                    after_token_estimate=token_estimate,
                    source_coverage=retrieval.source_coverage,
                    created_at=timestamp,
                    correlation_id=(
                        f"entity-compaction:{entity.entity_type.value}:{entity.entity_id}"
                    ),
                    entity_type=entity.entity_type,
                    entity_id=entity.entity_id,
                )
            )
            return EntityCompactionResult(
                entity,
                True,
                path,
                generation,
                len(retrieval.selected_claims),
                token_estimate,
            )


def _managed_content(claims: tuple) -> str:
    if not claims:
        return "- No active structured claims."
    return "\n".join(
        f"- [{claim.claim_id}] {claim.predicate}: "
        f"{json.dumps(claim.value, sort_keys=True, default=str)}"
        for claim in claims
    )


def _render_card(
    entity: MemoryEntity,
    generation: int,
    managed_content: str,
    updated_at: datetime,
) -> str:
    return (
        "---\n"
        "schema_version: 1\n"
        f"entity_type: {entity.entity_type.value}\n"
        f"entity_id: {entity.entity_id}\n"
        f"generation: {generation}\n"
        f"updated_at: {updated_at.isoformat()}\n"
        f"managed_hash: {_hash(managed_content)}\n"
        "---\n\n"
        f"# {entity.entity_type.value}: {entity.entity_id}\n\n"
        f"{managed_content}\n"
    )


def _hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


__all__ = ["EntityCompactionResult", "EntityMemoryCompactionService"]
