from __future__ import annotations

import duckdb

import vnalpha.commands.handlers.memory as memory_handler
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry


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
