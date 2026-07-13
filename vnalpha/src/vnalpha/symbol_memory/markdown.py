from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from vnalpha.symbol_memory.models import MemoryDocument
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.storage import symbol_card_path

_MANAGED_START = "<!-- openstock:managed:start current-snapshot -->"
_MANAGED_END = "<!-- openstock:managed:end current-snapshot -->"
_USER_START = "<!-- openstock:user:start -->"
_USER_END = "<!-- openstock:user:end -->"
_DOCUMENT_HASH_PATTERN = re.compile(r'(document_hash: ")[^"]*(")')


class MemoryCardError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedSymbolCard:
    symbol: str
    schema_version: int
    generation: int
    managed_hash: str
    document_hash: str
    managed_content: str
    user_content: str
    updated_at: datetime


def write_symbol_card(
    root: Path | None,
    symbol: str,
    *,
    managed_content: str,
    user_content: str | None = None,
    updated_at: datetime | None = None,
) -> MemoryDocument:
    canonical_symbol = normalize_symbol(symbol)
    path = symbol_card_path(root, canonical_symbol)
    previous = _load_existing(path)
    preserved_user_content = (
        previous.user_content if user_content is None and previous else user_content or ""
    )
    generation = 1 if previous is None else previous.generation + 1
    timestamp = updated_at or datetime.now(UTC)
    content, managed_hash, document_hash = _render_card(
        canonical_symbol,
        generation,
        managed_content,
        preserved_user_content,
        timestamp,
    )
    _atomic_write_text(path, content)
    return MemoryDocument(
        symbol=canonical_symbol,
        path=str(Path("knowledge") / "symbols" / f"{canonical_symbol}.md"),
        schema_version=1,
        generation=generation,
        managed_hash=managed_hash,
        document_hash=document_hash,
        token_estimate=_estimate_tokens(managed_content),
        last_compacted_at=None,
        updated_at=timestamp,
    )


def parse_symbol_card(content: str) -> ParsedSymbolCard:
    frontmatter, body = _split_frontmatter(content)
    values = _parse_frontmatter(frontmatter)
    try:
        symbol = normalize_symbol(values["entity_id"])
        schema_version = int(values["schema_version"])
        generation = int(values["generation"])
        updated_at = datetime.fromisoformat(values["updated_at"])
        managed_hash = values["managed_hash"]
        document_hash = values["document_hash"]
    except (KeyError, TypeError, ValueError) as exc:
        raise MemoryCardError("Malformed symbol-card frontmatter.") from exc
    if values.get("entity_type") != "symbol" or schema_version != 1:
        raise MemoryCardError("Unsupported symbol-card schema.")
    managed_content = _extract_region(body, _MANAGED_START, _MANAGED_END)
    user_content = _extract_region(body, _USER_START, _USER_END)
    if _hash(managed_content) != managed_hash:
        raise MemoryCardError("Managed symbol-card content hash does not match.")
    if _hash(_without_document_hash(content)) != document_hash:
        raise MemoryCardError("Symbol-card document hash does not match.")
    return ParsedSymbolCard(
        symbol=symbol,
        schema_version=schema_version,
        generation=generation,
        managed_hash=managed_hash,
        document_hash=document_hash,
        managed_content=managed_content,
        user_content=user_content,
        updated_at=updated_at,
    )


def _load_existing(path: Path) -> ParsedSymbolCard | None:
    if not path.exists():
        return None
    return parse_symbol_card(path.read_text(encoding="utf-8"))


def _render_card(
    symbol: str,
    generation: int,
    managed_content: str,
    user_content: str,
    updated_at: datetime,
) -> tuple[str, str, str]:
    managed_hash = _hash(managed_content)
    provisional = (
        "---\n"
        "schema_version: 1\n"
        f"document_id: symbol:{symbol}\n"
        "entity_type: symbol\n"
        f"entity_id: {symbol}\n"
        f"generation: {generation}\n"
        f"updated_at: {updated_at.isoformat()}\n"
        f'managed_hash: "{managed_hash}"\n'
        'document_hash: ""\n'
        "---\n\n"
        f"# {symbol}\n\n"
        "## Current snapshot\n\n"
        f"{_MANAGED_START}\n"
        f"{managed_content}{_MANAGED_END}\n\n"
        "## User notes\n\n"
        f"{_USER_START}\n"
        f"{user_content}{_USER_END}\n"
    )
    document_hash = _hash(provisional)
    return (
        provisional.replace('document_hash: ""', f'document_hash: "{document_hash}"'),
        managed_hash,
        document_hash,
    )


def _split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---\n"):
        raise MemoryCardError("Symbol card does not start with frontmatter.")
    closing_index = content.find("\n---\n", 4)
    if closing_index < 0:
        raise MemoryCardError("Symbol-card frontmatter is not terminated.")
    return content[4:closing_index], content[closing_index + 5 :]


def _parse_frontmatter(frontmatter: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key or key in values:
            raise MemoryCardError("Symbol-card frontmatter is malformed.")
        values[key] = value.strip().strip('"')
    return values


def _extract_region(content: str, start: str, end: str) -> str:
    start_index = content.find(start)
    end_index = content.find(end)
    if start_index < 0 or end_index < 0 or end_index < start_index:
        raise MemoryCardError("Symbol card is missing required managed markers.")
    region_start = start_index + len(start)
    if content[region_start : region_start + 1] != "\n":
        raise MemoryCardError("Symbol-card region boundary is malformed.")
    return content[region_start + 1 : end_index]


def _without_document_hash(content: str) -> str:
    return _DOCUMENT_HASH_PATTERN.sub(r"\1\2", content, count=1)


def _hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def _estimate_tokens(content: str) -> int:
    return max(0, (len(content) + 3) // 4)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


__all__ = [
    "MemoryCardError",
    "ParsedSymbolCard",
    "parse_symbol_card",
    "write_symbol_card",
]
