from __future__ import annotations

from datetime import datetime, timezone

import duckdb

from vnalpha.symbol_memory.markdown import write_symbol_card
from vnalpha.symbol_memory.recovery import inspect_symbol_card
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def _repository() -> SymbolMemoryRepository:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return SymbolMemoryRepository(connection)


def _time() -> datetime:
    return datetime(2026, 7, 13, 10, 30, tzinfo=timezone.utc)


def test_external_card_edit_is_reported_and_audited_without_overwrite(tmp_path) -> None:
    repository = _repository()
    document = write_symbol_card(
        tmp_path,
        "FPT",
        managed_content="- Initial observation",
        user_content="User note.",
        updated_at=_time(),
    )
    repository.upsert_document(document)
    path = tmp_path / document.path
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "\nManual change", encoding="utf-8")

    result = inspect_symbol_card(tmp_path, "FPT", repository, observed_at=_time())

    assert result.status == "externally_modified"
    assert path.read_text(encoding="utf-8").endswith("Manual change")
    assert [event.event_type for event in repository.list_events("FPT")] == [
        "DOCUMENT_EXTERNALLY_MODIFIED"
    ]


def test_malformed_card_is_quarantined_and_audited(tmp_path) -> None:
    repository = _repository()
    document = write_symbol_card(
        tmp_path,
        "FPT",
        managed_content="- Initial observation",
        updated_at=_time(),
    )
    repository.upsert_document(document)
    path = tmp_path / document.path
    path.write_text("not a symbol card", encoding="utf-8")

    result = inspect_symbol_card(tmp_path, "FPT", repository, observed_at=_time())

    assert result.status == "quarantined"
    assert not path.exists()
    assert result.quarantined_path is not None
    assert result.quarantined_path.exists()
    assert [event.event_type for event in repository.list_events("FPT")] == [
        "DOCUMENT_QUARANTINED"
    ]
