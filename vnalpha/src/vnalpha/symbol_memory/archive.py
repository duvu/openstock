from __future__ import annotations

import gzip
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from vnalpha.symbol_memory.models import MemoryEvent
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.storage import assert_knowledge_path, ensure_knowledge_layout


@dataclass(frozen=True, slots=True)
class MemoryArchiveRotation:
    symbol: str
    archived_event_count: int
    path: Path | None


class SymbolMemoryArchiveService:
    def __init__(self, repository: SymbolMemoryRepository, root: Path | None) -> None:
        self.repository = repository
        self.root = root

    def rotate(self, symbol: str) -> MemoryArchiveRotation:
        canonical_symbol = normalize_symbol(symbol)
        archived_ids = _read_archived_event_ids(self.root, canonical_symbol)
        pending = self._next_pending_events(canonical_symbol, archived_ids)
        if not pending:
            return MemoryArchiveRotation(canonical_symbol, 0, None)
        payload = "".join(
            json.dumps(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "evidence_ref": event.evidence_ref,
                    "content_hash": event.content_hash,
                    "observed_at": event.observed_at.isoformat()
                    if event.observed_at is not None
                    else None,
                    "as_of_date": event.as_of_date.isoformat()
                    if event.as_of_date is not None
                    else None,
                    "correlation_id": event.correlation_id,
                },
                sort_keys=True,
            )
            + "\n"
            for event in pending
        )
        layout = ensure_knowledge_layout(self.root)
        first_date = pending[0].created_at
        directory = (
            layout.archive_dir
            / "events"
            / f"{first_date.year:04d}"
            / f"{first_date.month:02d}"
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        target = directory / f"{canonical_symbol}-{digest}.jsonl.gz"
        _write_gzip(self.root, target, payload)
        _write_archived_event_ids(
            self.root,
            canonical_symbol,
            archived_ids | {event.event_id for event in pending},
        )
        return MemoryArchiveRotation(canonical_symbol, len(pending), target)

    def unarchived_event_count(self, symbol: str) -> int:
        canonical_symbol = normalize_symbol(symbol)
        archived_ids = _read_archived_event_ids(self.root, canonical_symbol)
        return self.repository.count_events(canonical_symbol) - len(archived_ids)

    def _next_pending_events(
        self, symbol: str, archived_ids: set[str]
    ) -> tuple[MemoryEvent, ...]:
        cursor: tuple[datetime, str] | None = None
        while True:
            events = self.repository.list_events_after(
                symbol, after=cursor, limit=10_000
            )
            if not events:
                return ()
            pending = tuple(
                event for event in events if event.event_id not in archived_ids
            )
            if pending:
                return pending
            cursor = (events[-1].created_at, events[-1].event_id)


def _manifest_path(root: Path | None, symbol: str) -> Path:
    return ensure_knowledge_layout(root).manifests_dir / f"{symbol}-archive-events.json"


def _read_archived_event_ids(root: Path | None, symbol: str) -> set[str]:
    path = _manifest_path(root, symbol)
    assert_knowledge_path(root, path)
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        event_ids = payload["event_ids"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Archived-event manifest is malformed.") from exc
    if not isinstance(event_ids, list):
        raise ValueError("Archived-event manifest is malformed.")
    return {str(event_id) for event_id in event_ids}


def _write_archived_event_ids(
    root: Path | None, symbol: str, event_ids: set[str]
) -> None:
    path = _manifest_path(root, symbol)
    _atomic_write(root, path, json.dumps({"event_ids": sorted(event_ids)}) + "\n")


def _write_gzip(root: Path | None, path: Path, payload: str) -> None:
    assert_knowledge_path(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        with gzip.GzipFile(fileobj=handle, mode="wb") as compressed:
            compressed.write(payload.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_write(root: Path | None, path: Path, content: str) -> None:
    assert_knowledge_path(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


__all__ = ["MemoryArchiveRotation", "SymbolMemoryArchiveService"]
