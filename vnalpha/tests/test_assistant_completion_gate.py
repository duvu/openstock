"""Completion-gate tests for Phase 5.9 assistant trace behavior."""

from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


def _fake_scan_llm() -> FakeLLMClient:
    return FakeLLMClient(
        responses=[
            (
                json.dumps(
                    {
                        "intent": "scan_candidates",
                        "confidence": 0.95,
                        "entities": {},
                    }
                ),
                {"prompt_tokens": 12, "completion_tokens": 6},
            ),
            (
                json.dumps(
                    {
                        "summary": "No candidates were returned by the persisted watchlist.",
                        "basis": "Based on watchlist.scan tool output.",
                        "risks_caveats": "Data may be missing.",
                        "tool_trace_summary": "watchlist.scan executed.",
                        "missing_data": ["empty watchlist"],
                    }
                ),
                {"prompt_tokens": 20, "completion_tokens": 10},
            ),
        ]
    )


def test_assistant_tool_trace_has_explicit_assistant_parent(conn):
    app = AssistantApp(conn, surface="cli", llm_client=_fake_scan_llm())

    app.ask("Show strongest candidates", date="2026-07-06")

    session_id = conn.execute(
        "SELECT assistant_session_id FROM assistant_session"
    ).fetchone()[0]
    row = conn.execute(
        """
        SELECT assistant_session_id, trace_parent_type, tool_name, status
        FROM tool_trace
        WHERE assistant_session_id = ?
        """,
        [session_id],
    ).fetchone()
    assert row == (session_id, "assistant", "watchlist.scan", "SUCCESS")


def test_assistant_llm_traces_store_model_and_usage(conn):
    app = AssistantApp(conn, surface="cli", llm_client=_fake_scan_llm())

    app.ask("Show strongest candidates", date="2026-07-06")

    rows = conn.execute(
        "SELECT stage, model, usage_json FROM llm_trace ORDER BY started_at"
    ).fetchall()
    assert [r[0] for r in rows] == ["classify", "synthesize"]
    assert all(r[1] for r in rows)
    assert all(json.loads(r[2])["prompt_tokens"] > 0 for r in rows)


def test_no_execute_creates_no_tool_trace(conn):
    app = AssistantApp(conn, surface="cli", llm_client=_fake_scan_llm())

    app.ask("Show strongest candidates", date="2026-07-06", no_execute=True)

    assert conn.execute("SELECT COUNT(*) FROM tool_trace").fetchone()[0] == 0


def test_unsafe_prompt_refused_before_tool_execution(conn):
    app = AssistantApp(conn, surface="cli", llm_client=_fake_scan_llm())

    app.ask("Buy FPT now", date="2026-07-06")

    assert (
        conn.execute("SELECT status FROM assistant_session").fetchone()[0] == "REFUSED"
    )
    assert conn.execute("SELECT COUNT(*) FROM tool_trace").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM llm_trace").fetchone()[0] == 0
