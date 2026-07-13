from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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
        symbols_dir,
        archive_dir / "events",
        quarantine_dir,
        manifests_dir,
        exports_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
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


__all__ = [
    "KnowledgePaths",
    "ensure_knowledge_layout",
    "resolve_knowledge_root",
    "symbol_card_path",
]
