from __future__ import annotations


def test_migrated_warehouse_connection_has_current_schema(
    migrated_warehouse_connection,
) -> None:
    tables = {
        row[0]
        for row in migrated_warehouse_connection.execute("SHOW TABLES").fetchall()
    }

    assert {"candidate_score", "research_session", "tool_trace"} <= tables


def test_migrated_warehouse_copies_do_not_share_mutations(
    migrated_warehouse_connection_factory,
) -> None:
    first = migrated_warehouse_connection_factory("first")
    second = migrated_warehouse_connection_factory("second")

    first.execute("INSERT INTO symbol_master (symbol, is_active) VALUES ('FPT', true)")

    assert second.execute("SELECT count(*) FROM symbol_master").fetchone() == (0,)
