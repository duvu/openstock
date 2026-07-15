"""Tests for Phase 5.9 assistant session and LLM trace persistence."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


def test_migrations_create_assistant_and_llm_tables(conn):
    tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
    assert "assistant_session" in tables
    assert "llm_trace" in tables


def test_migrations_idempotent(conn):
    run_migrations(conn=conn)  # second run
    tables = conn.execute("SHOW TABLES").fetchall()
    assert len(tables) == 49
