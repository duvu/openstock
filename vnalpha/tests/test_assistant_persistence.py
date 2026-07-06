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
    assert len(tables) == 19  # 8 phase1-5 + 3 phase5.8 + 2 phase5.9 + 6 phase6


# ---------------------------------------------------------------------------
# assistant_session tests
# ---------------------------------------------------------------------------

def test_create_assistant_session_returns_uuid(conn):
    sid = create_assistant_session(conn, surface="cli", user_prompt="hello")
    assert isinstance(sid, str)
    assert len(sid) == 36  # uuid4


def test_assistant_session_starts_running(conn):
    sid = create_assistant_session(conn, surface="cli", user_prompt="analyse VNM")
    row = conn.execute(
        "SELECT status FROM assistant_session WHERE assistant_session_id = ?", [sid]
    ).fetchone()
    assert row[0] == "RUNNING"


def test_finish_assistant_session_success(conn):
    sid = create_assistant_session(conn, surface="cli", user_prompt="price FPT")
    finish_assistant_session(conn, sid, status="SUCCESS")
    row = conn.execute(
        "SELECT status, finished_at FROM assistant_session WHERE assistant_session_id = ?",
        [sid],
    ).fetchone()
    assert row[0] == "SUCCESS"
    assert row[1] is not None


def test_finish_assistant_session_refused(conn):
    sid = create_assistant_session(conn, surface="cli", user_prompt="buy all stocks")
    finish_assistant_session(
        conn, sid, status="REFUSED", refusal_reason="out of scope"
    )
    row = conn.execute(
        "SELECT status, refusal_reason FROM assistant_session WHERE assistant_session_id = ?",
        [sid],
    ).fetchone()
    assert row[0] == "REFUSED"
    assert row[1] == "out of scope"


def test_finish_assistant_session_stores_plan_json(conn):
    sid = create_assistant_session(conn, surface="tui", user_prompt="show top picks")
    plan = {"steps": ["fetch", "score", "rank"]}
    finish_assistant_session(conn, sid, status="SUCCESS", plan=plan)
    row = conn.execute(
        "SELECT plan_json FROM assistant_session WHERE assistant_session_id = ?",
        [sid],
    ).fetchone()
    assert json.loads(row[0]) == plan


# ---------------------------------------------------------------------------
# llm_trace tests
# ---------------------------------------------------------------------------

def test_create_llm_trace_returns_uuid(conn):
    sid = create_assistant_session(conn, surface="cli", user_prompt="test")
    tid = create_llm_trace(conn, assistant_session_id=sid, stage="intent_classify")
    assert isinstance(tid, str)
    assert len(tid) == 36


def test_llm_trace_starts_running(conn):
    sid = create_assistant_session(conn, surface="cli", user_prompt="test")
    tid = create_llm_trace(conn, assistant_session_id=sid, stage="intent_classify", model="gpt-4o")
    row = conn.execute(
        "SELECT status, model FROM llm_trace WHERE llm_trace_id = ?", [tid]
    ).fetchone()
    assert row[0] == "RUNNING"
    assert row[1] == "gpt-4o"


def test_finish_llm_trace_stores_output(conn):
    sid = create_assistant_session(conn, surface="cli", user_prompt="test")
    tid = create_llm_trace(conn, assistant_session_id=sid, stage="answer_gen")
    output = {"answer": "FPT looks strong"}
    usage = {"prompt_tokens": 100, "completion_tokens": 50}
    finish_llm_trace(conn, tid, status="SUCCESS", output_summary=output, usage=usage)
    row = conn.execute(
        "SELECT status, output_summary_json, usage_json, finished_at FROM llm_trace WHERE llm_trace_id = ?",
        [tid],
    ).fetchone()
    assert row[0] == "SUCCESS"
    assert json.loads(row[1]) == output
    assert json.loads(row[2]) == usage
    assert row[3] is not None


# ---------------------------------------------------------------------------
# list_assistant_sessions tests
# ---------------------------------------------------------------------------

def test_list_assistant_sessions_ordered_by_time(conn):
    sid1 = create_assistant_session(conn, surface="cli", user_prompt="first")
    # Small sleep to ensure different timestamps
    time.sleep(0.01)
    sid2 = create_assistant_session(conn, surface="cli", user_prompt="second")
    sessions = list_assistant_sessions(conn)
    ids = [s["assistant_session_id"] for s in sessions]
    # Most recent first
    assert ids.index(sid2) < ids.index(sid1)


def test_list_assistant_sessions_limit(conn):
    for i in range(5):
        create_assistant_session(conn, surface="cli", user_prompt=f"query {i}")
    sessions = list_assistant_sessions(conn, limit=3)
    assert len(sessions) == 3
