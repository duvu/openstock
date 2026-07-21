from __future__ import annotations


def test_migrated_warehouse_copies_isolate_mutations(
    migrated_warehouse_connection_factory,
) -> None:
    first = migrated_warehouse_connection_factory("first")
    second = migrated_warehouse_connection_factory("second")

    first.execute("INSERT INTO symbol_master (symbol, is_active) VALUES ('FPT', true)")

    assert second.execute("SELECT count(*) FROM symbol_master").fetchone() == (0,)
