from __future__ import annotations

from datetime import datetime, timezone

from vnalpha.symbol_memory.storage import (
    ensure_knowledge_layout,
    symbol_card_path,
)


def _time() -> datetime:
    return datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)


def test_knowledge_layout_and_card_path_are_canonical_and_symbol_scoped(
    tmp_path,
) -> None:
    layout = ensure_knowledge_layout(tmp_path)

    assert layout.root == tmp_path / "knowledge"
    assert layout.symbols_dir == tmp_path / "knowledge" / "symbols"
    assert layout.archive_dir.is_dir()
    assert layout.quarantine_dir.is_dir()
    assert layout.manifests_dir.is_dir()
    assert layout.exports_dir.is_dir()
    assert symbol_card_path(tmp_path, " fpt ") == layout.symbols_dir / "FPT.md"
