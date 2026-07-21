from __future__ import annotations

import duckdb

from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.warehouse.migrations import run_migrations


def test_memory_command_registers_remember_show_and_redacted_status(tmp_path) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    registry = build_default_registry()

    remembered = registry.execute(
        parse('/memory remember FPT "private research note"'),
        conn=connection,
        root=tmp_path,
        session_id="memory-command-001",
    )
    status = registry.execute(parse("/memory status"), conn=connection, root=tmp_path)
    shown = registry.execute(parse("/memory show FPT"), conn=connection, root=tmp_path)

    assert "memory" in registry.names()
    assert remembered.status == "SUCCESS"
    assert status.status == "SUCCESS"
    assert "private research note" not in str(status.panels)
    assert shown.status == "SUCCESS"
    assert "FPT" in shown.summary
