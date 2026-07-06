"""Tests for Phase 5.8 warehouse schema additions and session/note repos (Tasks 4.1-4.6)."""

from __future__ import annotations

import pytest

from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.session_repo import (
    create_research_note,
    create_research_session,
    create_tool_trace,
    finish_research_session,
    finish_tool_trace,
    list_research_notes,
    list_research_sessions,
)


@pytest.fixture
def conn():
    """In-memory DuckDB connection with all migrations applied."""
    import duckdb
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


class TestSchemaAdditive:
    def test_phase5_tables_still_exist(self, conn):
        """Phase 5 tables must still be present after Phase 5.8 migration."""
        phase5_tables = [
            "ingestion_run", "symbol_master", "market_ohlcv_raw",
            "canonical_ohlcv", "feature_snapshot", "candidate_score",
            "daily_watchlist", "rejected_symbol",
        ]
        existing = {
            r[0] for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        for t in phase5_tables:
            assert t in existing, f"Missing Phase 5 table: {t}"

    def test_phase58_tables_created(self, conn):
        """Phase 5.8 tables must be present after migration."""
        phase58_tables = ["research_session", "tool_trace", "research_note"]
        existing = {
            r[0] for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        for t in phase58_tables:
            assert t in existing, f"Missing Phase 5.8 table: {t}"

    def test_migrations_idempotent(self, conn):
        """Running migrations twice should not fail (IF NOT EXISTS)."""
        run_migrations(conn=conn)  # second run


class TestResearchSession:
    def test_create_session(self, conn):
        session_id = create_research_session(
            conn, surface="cli", command_text="/scan VN30", command_name="scan"
        )
        assert isinstance(session_id, str) and len(session_id) == 36

    def test_finish_session_success(self, conn):
        sid = create_research_session(conn, surface="cli", command_text="/scan")
        finish_research_session(conn, sid, status="SUCCESS", result_summary={"count": 5})
        row = conn.execute(
            "SELECT status, result_summary_json FROM research_session WHERE session_id=?",
            [sid],
        ).fetchone()
        assert row[0] == "SUCCESS"
        assert "count" in row[1]

    def test_finish_session_failed(self, conn):
        sid = create_research_session(conn, surface="tui", command_text="/unknown")
        finish_research_session(
            conn, sid, status="FAILED", error={"error_type": "UnknownCommandError"}
        )
        row = conn.execute(
            "SELECT status, error_json FROM research_session WHERE session_id=?",
            [sid],
        ).fetchone()
        assert row[0] == "FAILED"
        assert "UnknownCommandError" in row[1]

    def test_list_sessions_ordered(self, conn):
        create_research_session(conn, surface="cli", command_text="/scan")
        create_research_session(conn, surface="cli", command_text="/explain FPT")
        sessions = list_research_sessions(conn, limit=10)
        assert len(sessions) == 2
        # Most recent first
        assert sessions[0]["command_text"] == "/explain FPT"


class TestToolTrace:
    def test_create_and_finish_trace(self, conn):
        sid = create_research_session(conn, surface="cli", command_text="/scan")
        trace_id = create_tool_trace(
            conn, session_id=sid, tool_name="watchlist.scan", input_data={"date": "2026-07-06"}
        )
        finish_tool_trace(conn, trace_id, status="SUCCESS", output_summary={"rows": 3})
        row = conn.execute(
            "SELECT status, output_summary_json FROM tool_trace WHERE tool_trace_id=?",
            [trace_id],
        ).fetchone()
        assert row[0] == "SUCCESS"
        assert "rows" in row[1]

    def test_trace_linked_to_session(self, conn):
        sid = create_research_session(conn, surface="cli", command_text="/scan")
        tid = create_tool_trace(conn, session_id=sid, tool_name="watchlist.scan")
        row = conn.execute(
            "SELECT session_id FROM tool_trace WHERE tool_trace_id=?", [tid]
        ).fetchone()
        assert row[0] == sid


class TestResearchNote:
    def test_create_note(self, conn):
        note_id = create_research_note(
            conn, symbol="FPT", note_text="Watch RS vs VNINDEX", tags=["rs", "watchlist"]
        )
        assert len(note_id) == 36

    def test_list_notes_by_symbol(self, conn):
        create_research_note(conn, symbol="FPT", note_text="note 1")
        create_research_note(conn, symbol="VNM", note_text="note 2")
        notes = list_research_notes(conn, symbol="FPT")
        assert len(notes) == 1
        assert notes[0]["note_text"] == "note 1"

    def test_list_all_notes(self, conn):
        create_research_note(conn, symbol="FPT", note_text="note A")
        create_research_note(conn, symbol="VNM", note_text="note B")
        notes = list_research_notes(conn)
        assert len(notes) == 2
