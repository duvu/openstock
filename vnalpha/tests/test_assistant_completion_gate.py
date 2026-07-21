"""Completion-gate tests for Phase 5.9 assistant trace behavior."""

from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import FakeLLMClient


@pytest.fixture
def conn(
    migrated_warehouse_connection: duckdb.DuckDBPyConnection,
) -> duckdb.DuckDBPyConnection:
    return migrated_warehouse_connection


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
