"""Tests for Phase 5.9 assistant session and LLM trace persistence."""
from __future__ import annotations

import json
import time

import duckdb
import pytest

from vnalpha.warehouse.assistant_repo import (
    create_assistant_session,
    create_llm_trace,
    finish_assistant_session,
    finish_llm_trace,
    list_assistant_sessions,
)
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
    assert len(tables) == 21  # 8 phase1-5 + 3 phase5.8 + 2 phase5.9 + 6 phase6 + 2 phase5.10