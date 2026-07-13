from __future__ import annotations

import duckdb

import vnalpha.commands.handlers.memory as memory_handler
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.warehouse.migrations import run_migrations


def test_memory_command_returns_structured_unavailable_when_schema_is_missing(
    tmp_path, monkeypatch
) -> None:
    connection = duckdb.connect(":memory:")

    def fail_migration(_connection) -> None:
        raise duckdb.Error("injected migration failure")

    monkeypatch.setattr(memory_handler, "run_migrations", fail_migration)

    result = build_default_registry().execute(
        parse("/memory status"),
        conn=connection,
        root=tmp_path,
    )

    assert result.status == "PARTIAL"
    assert result.metadata == {"availability": "unavailable"}


def test_rebuild_index_restores_card_from_structured_claims(tmp_path) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    connection.execute(
        "INSERT INTO memory_claim ("
        "claim_id, symbol, claim_type, predicate, value_json, status, pinned, "
        "confidence, observed_at, as_of_date, valid_from, valid_until, origin, "
        "source_refs_json, correlation_id, created_at, supersedes_claim_id, lifecycle_reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "rebuild-claim", "FPT", "durable_fact", "sector", '{"value":"Technology"}',
            "active", False, None, None, "2026-07-13", "2026-07-13", None,
            "validated_evidence", '["profile:FPT"]', "rebuild-test", "2026-07-13T00:00:00+00:00", None, None,
        ],
    )

    result = build_default_registry().execute(
        parse("/memory rebuild-index"), conn=connection, root=tmp_path
    )

    assert result.status == "SUCCESS"
    assert (tmp_path / "knowledge/symbols/FPT.md").exists()
