from __future__ import annotations

from datetime import datetime, timezone

import pytest

import vnalpha.symbol_memory.markdown as markdown_module
from vnalpha.symbol_memory.markdown import (
    parse_symbol_card,
    write_symbol_card,
)
from vnalpha.symbol_memory.storage import ensure_knowledge_layout, symbol_card_path


def _time() -> datetime:
    return datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)


def test_knowledge_layout_and_card_path_are_canonical_and_symbol_scoped(tmp_path) -> None:
    layout = ensure_knowledge_layout(tmp_path)

    assert layout.root == tmp_path / "knowledge"
    assert layout.symbols_dir == tmp_path / "knowledge" / "symbols"
    assert layout.archive_dir.is_dir()
    assert layout.quarantine_dir.is_dir()
    assert layout.manifests_dir.is_dir()
    assert layout.exports_dir.is_dir()
    assert symbol_card_path(tmp_path, " fpt ") == layout.symbols_dir / "FPT.md"


def test_symbol_card_round_trips_versioned_frontmatter_and_user_region(tmp_path) -> None:
    user_content = "Watch the next reporting period.\nDo not turn this into a fact."
    document = write_symbol_card(
        tmp_path,
        "FPT",
        managed_content="- Current score: 0.82\n- Source: `candidate_score:FPT:2026-07-13`",
        user_content=user_content,
        updated_at=_time(),
    )

    parsed = parse_symbol_card((tmp_path / document.path).read_text(encoding="utf-8"))

    assert parsed.symbol == "FPT"
    assert parsed.schema_version == 1
    assert parsed.generation == 1
    assert parsed.managed_content.startswith("- Current score")
    assert parsed.user_content == user_content
    assert document.document_hash == parsed.document_hash
    assert document.managed_hash == parsed.managed_hash


def test_card_update_preserves_existing_user_region_byte_for_byte_and_bumps_generation(
    tmp_path,
) -> None:
    user_content = "Keep this precise.\n\nNo automated rewrite.\n"
    first = write_symbol_card(
        tmp_path,
        "FPT",
        managed_content="- First observation",
        user_content=user_content,
        updated_at=_time(),
    )
    second = write_symbol_card(
        tmp_path,
        "FPT",
        managed_content="- Newer observation",
        updated_at=_time(),
    )
    parsed = parse_symbol_card((tmp_path / second.path).read_text(encoding="utf-8"))

    assert second.generation == first.generation + 1
    assert second.document_hash != first.document_hash
    assert parsed.user_content == user_content


def test_failed_atomic_replace_keeps_existing_card_intact(tmp_path, monkeypatch) -> None:
    first = write_symbol_card(
        tmp_path,
        "FPT",
        managed_content="- Existing observation",
        user_content="Preserve this.",
        updated_at=_time(),
    )
    card_path = tmp_path / first.path
    previous_content = card_path.read_text(encoding="utf-8")

    def fail_replace(source, destination) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(markdown_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        write_symbol_card(
            tmp_path,
            "FPT",
            managed_content="- Replacement observation",
            updated_at=_time(),
        )

    assert card_path.read_text(encoding="utf-8") == previous_content
