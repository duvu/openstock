from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from vnalpha.symbol_memory.markdown import (
    MemoryCardError,
    ParsedSymbolCard,
    document_hash_for_content,
    parse_symbol_card,
)
from vnalpha.symbol_memory.models import ClaimOrigin, MemoryDocument, MemoryEvent
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.storage import (
    assert_knowledge_path,
    ensure_knowledge_layout,
    symbol_card_path,
)


@dataclass(frozen=True, slots=True)
class SymbolCardInspection:
    status: str
    card: ParsedSymbolCard | None
    quarantined_path: Path | None = None


def inspect_symbol_card(
    root: Path | None,
    symbol: str,
    repository: SymbolMemoryRepository,
    *,
    observed_at: datetime | None = None,
) -> SymbolCardInspection:
    canonical_symbol = normalize_symbol(symbol)
    path = symbol_card_path(root, canonical_symbol)
    assert_knowledge_path(root, path)
    if not path.exists():
        return SymbolCardInspection(status="missing", card=None)
    timestamp = observed_at or datetime.now(UTC)
    content = path.read_text(encoding="utf-8")
    try:
        card = parse_symbol_card(content, validate_hashes=False)
    except MemoryCardError:
        quarantined_path = _quarantine(path, root, canonical_symbol, timestamp)
        _record_document_event(
            repository,
            canonical_symbol,
            "DOCUMENT_QUARANTINED",
            content,
            timestamp,
        )
        return SymbolCardInspection(
            status="quarantined",
            card=None,
            quarantined_path=quarantined_path,
        )
    document = repository.get_document(canonical_symbol)
    if document is None:
        try:
            card = parse_symbol_card(content)
        except MemoryCardError:
            quarantined_path = _quarantine(path, root, canonical_symbol, timestamp)
            _record_document_event(
                repository,
                canonical_symbol,
                "DOCUMENT_QUARANTINED",
                content,
                timestamp,
            )
            return SymbolCardInspection(
                status="quarantined",
                card=None,
                quarantined_path=quarantined_path,
            )
    if document is not None and document.document_hash != document_hash_for_content(
        content
    ):
        _record_document_event(
            repository,
            canonical_symbol,
            "DOCUMENT_EXTERNALLY_MODIFIED",
            content,
            timestamp,
        )
        return SymbolCardInspection(status="externally_modified", card=card)
    return SymbolCardInspection(status="valid", card=card)


def repair_symbol_card(
    root: Path | None,
    symbol: str,
    repository: SymbolMemoryRepository,
    *,
    observed_at: datetime | None = None,
) -> SymbolCardInspection:
    inspection = inspect_symbol_card(root, symbol, repository, observed_at=observed_at)
    if inspection.status != "valid" or inspection.card is None:
        return inspection
    existing = repository.get_document(inspection.card.symbol)
    if (
        existing is not None
        and existing.document_hash == inspection.card.document_hash
        and existing.managed_hash == inspection.card.managed_hash
    ):
        return inspection
    repository.upsert_document(
        MemoryDocument(
            symbol=inspection.card.symbol,
            path=str(Path("knowledge") / "symbols" / f"{inspection.card.symbol}.md"),
            schema_version=inspection.card.schema_version,
            generation=inspection.card.generation,
            managed_hash=inspection.card.managed_hash,
            document_hash=inspection.card.document_hash,
            token_estimate=(len(inspection.card.managed_content) + 3) // 4,
            last_compacted_at=inspection.card.updated_at,
            updated_at=inspection.card.updated_at,
        )
    )
    return SymbolCardInspection(status="reindexed", card=inspection.card)


def _quarantine(
    path: Path, root: Path | None, symbol: str, timestamp: datetime
) -> Path:
    layout = ensure_knowledge_layout(root)
    target = layout.quarantine_dir / (
        f"{symbol}-{timestamp.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}-"
        f"{uuid4().hex[:8]}.md"
    )
    path.replace(target)
    return target


def _record_document_event(
    repository: SymbolMemoryRepository,
    symbol: str,
    event_type: str,
    content: str,
    timestamp: datetime,
) -> None:
    repository.append_event(
        MemoryEvent(
            event_id=f"memory-document-{uuid4().hex}",
            symbol=symbol,
            event_type=event_type,
            evidence_ref=f"knowledge/symbols/{symbol}.md",
            content_hash="sha256:"
            + hashlib.sha256(content.encode("utf-8")).hexdigest(),
            observed_at=timestamp,
            as_of_date=timestamp.date(),
            origin=ClaimOrigin.USER_CORRECTION,
            correlation_id=f"memory-document-{uuid4().hex}",
            created_at=timestamp,
        )
    )


__all__ = ["SymbolCardInspection", "inspect_symbol_card", "repair_symbol_card"]
