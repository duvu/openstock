from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from vnalpha.symbol_memory.models import MemoryEntity, MemoryEntityType
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.workspace_context.storage import resolve_workspace_root


@dataclass(frozen=True, slots=True)
class KnowledgePaths:
    root: Path
    symbols_dir: Path
    archive_dir: Path
    quarantine_dir: Path
    manifests_dir: Path
    exports_dir: Path


class KnowledgePathError(ValueError):
    pass


def resolve_knowledge_root(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root).expanduser() / "knowledge"
    override = os.environ.get("VNALPHA_KNOWLEDGE_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    return resolve_workspace_root().parent / "knowledge"


def ensure_knowledge_layout(root: Path | None = None) -> KnowledgePaths:
    knowledge_root = resolve_knowledge_root(root)
    symbols_dir = knowledge_root / "symbols"
    archive_dir = knowledge_root / "archive"
    quarantine_dir = knowledge_root / "quarantine"
    manifests_dir = knowledge_root / "manifests"
    exports_dir = knowledge_root / "exports"
    for path in (
        knowledge_root,
        symbols_dir,
        archive_dir,
        archive_dir / "events",
        quarantine_dir,
        manifests_dir,
        exports_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise KnowledgePathError(
                f"Knowledge storage directory must not be a symlink: {path.name}"
            )
    return KnowledgePaths(
        root=knowledge_root,
        symbols_dir=symbols_dir,
        archive_dir=archive_dir,
        quarantine_dir=quarantine_dir,
        manifests_dir=manifests_dir,
        exports_dir=exports_dir,
    )


def symbol_card_path(root: Path | None, symbol: str) -> Path:
    return ensure_knowledge_layout(root).symbols_dir / f"{normalize_symbol(symbol)}.md"


def entity_card_path(root: Path | None, entity: MemoryEntity) -> Path:
    if entity.entity_type is MemoryEntityType.SYMBOL:
        return symbol_card_path(root, entity.entity_id)
    safe_id = entity.entity_id.replace(":", "--")
    return (
        ensure_knowledge_layout(root).root
        / "entities"
        / entity.entity_type.value.lower()
        / f"{safe_id}.md"
    )


def assert_knowledge_path(root: Path | None, path: Path) -> None:
    layout = ensure_knowledge_layout(root)
    try:
        relative = path.relative_to(layout.root)
    except ValueError as exc:
        raise KnowledgePathError("Knowledge path escapes the storage root.") from exc
    current = layout.root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise KnowledgePathError(
                f"Knowledge storage path must not be a symlink: {current.name}"
            )


__all__ = [
    "KnowledgePaths",
    "KnowledgePathError",
    "assert_knowledge_path",
    "ensure_knowledge_layout",
    "entity_card_path",
    "resolve_knowledge_root",
    "symbol_card_path",
]
