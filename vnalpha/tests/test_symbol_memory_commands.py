from __future__ import annotations

import duckdb
import pytest

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


def test_memory_correct_and_pin_commands_preserve_claim_audit_state(tmp_path) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    registry = build_default_registry()
    registry.execute(
        parse('/memory remember FPT "watch source quality"'),
        conn=connection,
        root=tmp_path,
    )
    claim_id = connection.execute(
        "SELECT claim_id FROM memory_claim WHERE symbol = 'FPT'"
    ).fetchone()[0]

    pinned = registry.execute(
        parse(f"/memory pin {claim_id}"), conn=connection, root=tmp_path
    )
    corrected = registry.execute(
        parse(f'/memory correct FPT {claim_id} "user correction"'),
        conn=connection,
        root=tmp_path,
    )
    unpinned = registry.execute(
        parse(f"/memory unpin {claim_id}"), conn=connection, root=tmp_path
    )

    assert pinned.status == "SUCCESS"
    assert corrected.status == "SUCCESS"
    assert unpinned.status == "SUCCESS"
    assert connection.execute(
        "SELECT status, pinned FROM memory_claim WHERE claim_id = ?", [claim_id]
    ).fetchone() == ("rejected", False)
    assert {
        row[0]
        for row in connection.execute(
            "SELECT event_type FROM memory_event WHERE evidence_ref = ?", [claim_id]
        ).fetchall()
    } == {"CLAIM_PINNED", "CLAIM_UNPINNED", "USER_CORRECTION_RECORDED"}


def test_memory_inspection_compaction_repair_and_rebuild_commands(tmp_path) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    registry = build_default_registry()
    registry.execute(
        parse('/memory remember FPT "private note"'),
        conn=connection,
        root=tmp_path,
    )
    card_path = tmp_path / "knowledge" / "symbols" / "FPT.md"
    before_dry_run = card_path.read_text(encoding="utf-8")

    conflicts = registry.execute(
        parse("/memory conflicts FPT"), conn=connection, root=tmp_path
    )
    sources = registry.execute(
        parse("/memory sources FPT"), conn=connection, root=tmp_path
    )
    dry_run = registry.execute(
        parse("/memory compact FPT --dry-run"), conn=connection, root=tmp_path
    )
    execute = registry.execute(
        parse("/memory compact FPT"), conn=connection, root=tmp_path
    )
    repair = registry.execute(
        parse("/memory repair FPT"), conn=connection, root=tmp_path
    )
    rebuilt = registry.execute(
        parse("/memory rebuild-index"), conn=connection, root=tmp_path
    )

    assert conflicts.status == "SUCCESS"
    assert sources.status == "SUCCESS"
    assert dry_run.status == "SUCCESS"
    assert card_path.read_text(encoding="utf-8") == before_dry_run
    assert execute.status == "SUCCESS"
    assert repair.summary == "Memory card is valid."
    assert rebuilt.summary == "Rebuilt 1 symbol card index entries."
    assert {
        "before_token_estimate",
        "after_token_estimate",
        "conflicted_claim_count",
    } <= set(dry_run.metadata)
    assert sources.metadata["sources"] == []


def test_memory_rebuild_respects_the_root_maintenance_lock(tmp_path) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    registry = build_default_registry()

    from vnalpha.symbol_memory.locking import (
        MemoryLockContentionError,
        root_maintenance_lock,
    )

    with root_maintenance_lock(tmp_path):
        with pytest.raises(MemoryLockContentionError):
            registry.execute(
                parse("/memory rebuild-index"), conn=connection, root=tmp_path
            )


def test_memory_remember_acquires_the_symbol_lock_before_persisting(tmp_path) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    registry = build_default_registry()

    from vnalpha.symbol_memory.locking import (
        MemoryLockContentionError,
        symbol_memory_lock,
    )

    with symbol_memory_lock(tmp_path, "FPT"):
        with pytest.raises(MemoryLockContentionError):
            registry.execute(
                parse('/memory remember FPT "must not persist without card lock"'),
                conn=connection,
                root=tmp_path,
            )

    assert connection.execute("SELECT COUNT(*) FROM memory_event").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM memory_claim").fetchone()[0] == 0


@pytest.mark.parametrize("command", ("pin", "correct"))
def test_memory_claim_mutations_acquire_the_symbol_lock(tmp_path, command) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    registry = build_default_registry()
    registry.execute(
        parse('/memory remember FPT "lock test"'), conn=connection, root=tmp_path
    )
    claim_id = connection.execute(
        "SELECT claim_id FROM memory_claim WHERE symbol = 'FPT'"
    ).fetchone()[0]

    from vnalpha.symbol_memory.locking import (
        MemoryLockContentionError,
        symbol_memory_lock,
    )

    command_line = (
        f"/memory pin {claim_id}"
        if command == "pin"
        else f'/memory correct FPT {claim_id} "must wait for the lock"'
    )
    with symbol_memory_lock(tmp_path, "FPT"):
        with pytest.raises(MemoryLockContentionError):
            registry.execute(parse(command_line), conn=connection, root=tmp_path)

    status, pinned = connection.execute(
        "SELECT status, pinned FROM memory_claim WHERE claim_id = ?", [claim_id]
    ).fetchone()
    assert status == "active"
    assert pinned is False
    assert connection.execute("SELECT COUNT(*) FROM memory_event").fetchone()[0] == 1


def test_memory_status_exposes_operational_state_without_note_bodies(tmp_path) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    registry = build_default_registry()
    registry.execute(
        parse('/memory remember FPT "private note body"'),
        conn=connection,
        root=tmp_path,
    )
    connection.execute(
        "UPDATE memory_claim SET status = 'conflicted' WHERE symbol = 'FPT'"
    )

    status = registry.execute(parse("/memory status"), conn=connection, root=tmp_path)
    content = status.panels[0].content

    assert status.status == "SUCCESS"
    assert {
        "availability",
        "conflicts",
        "freshness",
        "token_budgets",
        "compaction",
    } <= set(content)
    assert "private note body" not in str(content)


def test_memory_maintain_is_an_operational_command(tmp_path) -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    registry = build_default_registry()
    registry.execute(
        parse('/memory remember FPT "maintenance subject"'),
        conn=connection,
        root=tmp_path,
    )

    result = registry.execute(
        parse("/memory maintain 2026-07-13"), conn=connection, root=tmp_path
    )

    assert result.status == "SUCCESS"
    assert result.metadata == {"processed_symbols": ["FPT"], "failed_symbols": []}
