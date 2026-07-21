"""Tests for Phase 5.10 chat persistence (chat_session + chat_message)."""

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
# Schema creation tests
# ---------------------------------------------------------------------------


def test_migrations_create_chat_tables(conn):
    tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
    assert "chat_session" in tables
    assert "chat_message" in tables


# ---------------------------------------------------------------------------
# chat_session tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# chat_message tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# list_chat_messages ordering tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# clear_visible_messages tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Full transcript test
# ---------------------------------------------------------------------------
